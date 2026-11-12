"""Self-service subscription payment with Razorpay (one payment per monthly/yearly period)."""
import json
import logging
import re
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Literal

from starlette.concurrency import run_in_threadpool
from fastapi import BackgroundTasks, APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import Principal, require_roles
from app.billing import razorpay
from app.core import email_templates, mailer
from app.core.audit import audit
from app.core.subscriptions import _latest_subscription, subscription_state
from app.db import get_db, set_tenant_context
from app.core.config import settings
from app.models import AutoRenewal, Invoice, PaymentOrder, RazorpayPlan, Restaurant, Subscription, Tenant, TenantProfile, User, now_utc
from app.platform_admin.router import _invoice_json, _prices, build_invoice

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])
log = logging.getLogger(__name__)
OWNER = Depends(require_roles("owner"))
PAYMENT_ID = re.compile(r"^pay_[A-Za-z0-9]+$")
ORDER_ID = re.compile(r"^order_[A-Za-z0-9]+$")


class CheckoutInput(BaseModel):
    billing_cycle: Literal["monthly", "yearly"]


class AutoRenewVerify(BaseModel):
    razorpay_payment_id: str
    razorpay_subscription_id: str
    razorpay_signature: str


class VerifyInput(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


def _is_yearly(inv: Invoice) -> bool:
    return (inv.period_end - inv.period_start).days > 60


def mark_paid(db: Session, tenant_id: int, razorpay_order_id: str, payment_id: str, amount_paise: int,
              principal: Principal | None = None) -> PaymentOrder | None:
    """Idempotent: the checkout callback and the webhook can both arrive, and only the first one counts."""
    po = db.scalar(select(PaymentOrder).where(
        PaymentOrder.tenant_id == tenant_id, PaymentOrder.razorpay_order_id == razorpay_order_id).with_for_update())
    if not po:
        return None
    if po.status in ("paid", "duplicate"):
        return po
    if amount_paise != po.amount_paise:
        raise HTTPException(409, "Paid amount does not match the invoice")
    inv = db.scalar(select(Invoice).where(Invoice.id == po.invoice_id, Invoice.tenant_id == tenant_id))
    po.razorpay_payment_id, po.paid_at = payment_id, now_utc()
    if not inv or inv.status == "paid":
        po.status = "duplicate"  # the invoice was already settled: needs a manual refund
        log.warning("Duplicate payment %s for order %s (tenant %s)", payment_id, razorpay_order_id, tenant_id)
        return po
    po.status = "paid"
    inv.status, inv.paid_at = "paid", now_utc()
    sub = _latest_subscription(db, tenant_id)
    if sub:
        sub.status = "active"
        sub.billing_cycle = "yearly" if _is_yearly(inv) else "monthly"
        sub.ends_at = datetime.combine(inv.period_end, time(23, 59, 59), tzinfo=timezone.utc)
    audit(db, principal or Principal(0, tenant_id, "system", "razorpay"), "subscription_paid", "invoice", inv.id,
          {"payment_id": payment_id, "total": str(inv.total)})
    return po


def _queue_receipt(db: Session, background: BackgroundTasks, invoice_id: int, tenant_id: int) -> None:
    inv = db.get(Invoice, invoice_id)
    owner = db.scalar(select(User).where(User.tenant_id == tenant_id, User.role == "owner").order_by(User.id))
    if inv and owner:
        subject, body = email_templates.receipt(owner.full_name or "there", inv.number, float(inv.total),
                                                inv.period_start.isoformat(), inv.period_end.isoformat())
        background.add_task(mailer.send_safe, owner.email, subject, body)


@router.get("/status")
def billing_status(principal: Principal = OWNER, db: Session = Depends(get_db)):
    price = _prices(db)[_latest_plan(db, principal.tenant_id)]
    invoices = db.scalars(select(Invoice).where(Invoice.tenant_id == principal.tenant_id).order_by(Invoice.id.desc()).limit(24)).all()
    return {
        "subscription": subscription_state(db, principal.tenant_id),
        "payments_enabled": razorpay.configured(),
        "price": {"monthly": float(price.price_inr), "yearly": float(price.yearly_price_inr), "gst_percent": float(price.gst_percent)},
        "invoices": [_invoice_json(i) for i in invoices],
        "autorenew": _autorenew_json(_live_autorenew(db, principal.tenant_id)) or _autorenew_json(_last_autorenew(db, principal.tenant_id)),
    }


def _latest_plan(db: Session, tenant_id: int) -> str:
    from app.core.subscriptions import current_plan_name
    return current_plan_name(db, tenant_id)


@router.get("/invoices/{invoice_id}/tax-invoice")
def tax_invoice(invoice_id: int, principal: Principal = OWNER, db: Session = Depends(get_db)):
    inv = db.scalar(select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == principal.tenant_id))
    if not inv or inv.status != "paid":
        raise HTTPException(404, "Paid invoice not found")
    profile = db.scalar(select(TenantProfile).where(TenantProfile.tenant_id == principal.tenant_id))
    tenant = db.get(Tenant, principal.tenant_id)
    s = settings
    same_state = bool(profile and s.seller_state_code and profile.state_code.upper() == s.seller_state_code.upper())
    half = (inv.gst / 2).quantize(Decimal("0.01"))
    tax = {"cgst": float(half), "sgst": float(inv.gst - half), "igst": 0.0} if same_state else {"cgst": 0.0, "sgst": 0.0, "igst": float(inv.gst)}
    return {
        "number": inv.number, "date": (inv.paid_at or inv.created_at).date().isoformat(),
        "draft": not (s.seller_legal_name and s.seller_gstin),
        "seller": {"name": s.seller_legal_name or "[Your legal business name]", "gstin": s.seller_gstin or "[Your GSTIN]",
                   "address": s.seller_address or "[Your registered address]"},
        "buyer": {"name": tenant.name if tenant else "", "gstin": profile.gstin if profile else None,
                  "address": f"{profile.address_line}, {profile.city} {profile.pincode}" if profile else "",
                  "state_code": profile.state_code if profile else ""},
        "sac": s.seller_sac, "description": f"RestoIQ POS subscription ({inv.plan_name}), {inv.outlets} outlet(s)",
        "period_start": inv.period_start.isoformat(), "period_end": inv.period_end.isoformat(),
        "subtotal": float(inv.subtotal), "gst": float(inv.gst), "total": float(inv.total), **tax,
    }


@router.post("/checkout")
def checkout(body: CheckoutInput, principal: Principal = OWNER, db: Session = Depends(get_db)):
    yearly = body.billing_cycle == "yearly"
    sub = _latest_subscription(db, principal.tenant_id)
    start = date.today()
    if sub and sub.status == "trial" and sub.ends_at and sub.ends_at > now_utc():
        start = sub.ends_at.date()  # paying early never wastes free-trial days
    elif sub and sub.status == "active" and sub.ends_at and sub.ends_at > now_utc():
        start = sub.ends_at.date()  # renewing early extends from the current period end
    pending = list(db.scalars(select(Invoice).where(Invoice.tenant_id == principal.tenant_id, Invoice.status == "pending")
                              .order_by(Invoice.id.desc())))
    inv = next((i for i in pending if _is_yearly(i) == yearly and i.period_start == start), None)
    for other in pending:
        if other is not inv:
            other.status = "void"
    if not inv:
        inv = build_invoice(db, principal.tenant_id, yearly, start)
    amount = int((inv.total * 100).to_integral_value())
    po = db.scalar(select(PaymentOrder).where(PaymentOrder.invoice_id == inv.id, PaymentOrder.status == "created")
                   .order_by(PaymentOrder.id.desc()))
    if not po:
        order = razorpay.call("POST", "/orders", json={
            "amount": amount, "currency": "INR", "receipt": inv.number,
            "notes": {"tenant_id": str(principal.tenant_id), "invoice_id": str(inv.id)},
        })
        po = PaymentOrder(tenant_id=principal.tenant_id, invoice_id=inv.id, razorpay_order_id=order["id"], amount_paise=amount)
        db.add(po)
        db.flush()
    user = db.get(User, principal.user_id)
    return {"key_id": razorpay.settings.razorpay_key_id, "razorpay_order_id": po.razorpay_order_id, "amount": amount,
            "currency": "INR", "invoice_number": inv.number, "email": user.email if user else None,
            "description": f"RestoIQ POS {'yearly' if yearly else 'monthly'} · {inv.outlets} outlet(s)"}


@router.post("/verify")
def verify(body: VerifyInput, background: BackgroundTasks, principal: Principal = OWNER, db: Session = Depends(get_db)):
    if not (ORDER_ID.match(body.razorpay_order_id) and PAYMENT_ID.match(body.razorpay_payment_id)):
        raise HTTPException(422, "Invalid payment details")
    po = db.scalar(select(PaymentOrder).where(
        PaymentOrder.tenant_id == principal.tenant_id, PaymentOrder.razorpay_order_id == body.razorpay_order_id))
    if not po:
        raise HTTPException(404, "Payment order not found")
    if not razorpay.checkout_signature_ok(body.razorpay_order_id, body.razorpay_payment_id, body.razorpay_signature):
        raise HTTPException(400, "Invalid payment signature")
    payment = razorpay.call("GET", f"/payments/{body.razorpay_payment_id}")
    if payment.get("order_id") != po.razorpay_order_id or payment.get("currency") != "INR" or payment.get("amount") != po.amount_paise:
        raise HTTPException(400, "Payment does not match this invoice")
    if payment.get("status") == "authorized":
        payment = razorpay.call("POST", f"/payments/{body.razorpay_payment_id}/capture", json={"amount": po.amount_paise, "currency": "INR"})
    if payment.get("status") != "captured":
        raise HTTPException(409, "Payment is not completed yet. If money was deducted it will be applied automatically.")
    was_new = po.status == "created"
    mark_paid(db, principal.tenant_id, po.razorpay_order_id, body.razorpay_payment_id, po.amount_paise, principal)
    if was_new:
        _queue_receipt(db, background, po.invoice_id, principal.tenant_id)
    return {"status": "paid", "subscription": subscription_state(db, principal.tenant_id)}


@router.post("/webhook")
async def webhook(request: Request, background: BackgroundTasks, db: Session = Depends(get_db)):
    """Razorpay server-to-server callback: settles the invoice even if the customer closes the browser."""
    raw = await request.body()
    return await run_in_threadpool(_webhook, request, raw, background, db)


def _webhook(request: Request, raw: bytes, background: BackgroundTasks, db: Session):
    if not razorpay.settings.razorpay_webhook_secret:
        raise HTTPException(503, "Webhook is not configured")
    if not razorpay.webhook_signature_ok(raw, request.headers.get("X-Razorpay-Signature", "")):
        raise HTTPException(400, "Invalid signature")
    event = json.loads(raw)
    if str(event.get("event", "")).startswith("subscription."):
        handle_subscription_event(db, background, event)
        return {"ok": True}
    if event.get("event") not in ("payment.captured", "order.paid"):
        return {"ok": True}
    payment = (event.get("payload", {}).get("payment") or {}).get("entity") or {}
    order_id, payment_id = payment.get("order_id"), payment.get("id")
    if not (order_id and payment_id and ORDER_ID.match(order_id) and PAYMENT_ID.match(payment_id)):
        return {"ok": True}
    order = razorpay.call("GET", f"/orders/{order_id}")  # the tenant comes from notes we set when creating the order
    tenant_id = int((order.get("notes") or {}).get("tenant_id", 0) or 0)
    if not tenant_id:
        return {"ok": True}
    set_tenant_context(db, tenant_id)
    existing = db.scalar(select(PaymentOrder.status).where(PaymentOrder.tenant_id == tenant_id, PaymentOrder.razorpay_order_id == order_id))
    po = mark_paid(db, tenant_id, order_id, payment_id, int(payment.get("amount", 0)))
    if po and existing == "created" and po.status == "paid":
        _queue_receipt(db, background, po.invoice_id, tenant_id)
    return {"ok": True}


# ---- Auto-renew (Razorpay Subscriptions) -------------------------------------------------

LIVE = ("created", "authenticated", "active")
SUB_ID = re.compile(r"^sub_[A-Za-z0-9]+$")


def _live_autorenew(db: Session, tenant_id: int) -> AutoRenewal | None:
    return db.scalar(select(AutoRenewal).where(AutoRenewal.tenant_id == tenant_id, AutoRenewal.status.in_(("authenticated", "active"))).order_by(AutoRenewal.id.desc()))


def _last_autorenew(db: Session, tenant_id: int) -> AutoRenewal | None:
    return db.scalar(select(AutoRenewal).where(AutoRenewal.tenant_id == tenant_id).order_by(AutoRenewal.id.desc()))


def _autorenew_json(a: AutoRenewal | None) -> dict | None:
    return None if not a else {"status": a.status, "billing_cycle": a.billing_cycle, "amount": a.amount_paise / 100}


def _renewal_amount(db: Session, tenant_id: int, yearly: bool) -> int:
    price = _prices(db)[_latest_plan(db, tenant_id)]
    outlets = max(db.scalar(select(func.count()).select_from(Restaurant).where(Restaurant.tenant_id == tenant_id)) or 0, 1)
    subtotal = (price.yearly_price_inr if yearly else price.price_inr) * outlets
    return int((subtotal * (100 + price.gst_percent)).quantize(Decimal("1")))  # paise, GST included


def _razorpay_plan(db: Session, cycle: str, amount: int) -> str:
    row = db.scalar(select(RazorpayPlan).where(RazorpayPlan.billing_cycle == cycle, RazorpayPlan.amount_paise == amount))
    if row:
        return row.razorpay_plan_id
    created = razorpay.call("POST", "/plans", json={
        "period": "yearly" if cycle == "yearly" else "monthly", "interval": 1,
        "item": {"name": f"RestoIQ POS {cycle}", "amount": amount, "currency": "INR"}})
    db.add(RazorpayPlan(billing_cycle=cycle, amount_paise=amount, razorpay_plan_id=created["id"]))
    db.flush()
    return created["id"]


def settle_charge(db: Session, tenant_id: int, ar: AutoRenewal, payment_id: str, amount_paise: int) -> bool:
    """Record one automatic charge as a paid invoice and extend the plan. Idempotent per payment."""
    key = f"sub_{payment_id}"[:40]
    if db.scalar(select(PaymentOrder.id).where(PaymentOrder.razorpay_order_id == key)):
        return False
    yearly = ar.billing_cycle == "yearly"
    sub = _latest_subscription(db, tenant_id)
    start = date.today()
    if sub and sub.status in ("trial", "active") and sub.ends_at and sub.ends_at > now_utc():
        start = sub.ends_at.date()
    total = (Decimal(amount_paise) / 100).quantize(Decimal("0.01"))
    price = _prices(db)[_latest_plan(db, tenant_id)]
    subtotal = (total / (1 + price.gst_percent / 100)).quantize(Decimal("0.01"))
    outlets = max(db.scalar(select(func.count()).select_from(Restaurant).where(Restaurant.tenant_id == tenant_id)) or 0, 1)
    inv = Invoice(tenant_id=tenant_id, number="PENDING", plan_name=_latest_plan(db, tenant_id), outlets=outlets, subtotal=subtotal,
                  gst=total - subtotal, total=total, status="pending", period_start=start,
                  period_end=start + timedelta(days=365 if yearly else 30))
    db.add(inv)
    db.flush()
    inv.number = f"INV-{date.today():%Y%m}-{inv.id:05d}"
    db.add(PaymentOrder(tenant_id=tenant_id, invoice_id=inv.id, razorpay_order_id=key, amount_paise=amount_paise))
    db.flush()
    mark_paid(db, tenant_id, key, payment_id, amount_paise)
    return True


@router.post("/autorenew")
def start_autorenew(body: CheckoutInput, principal: Principal = OWNER, db: Session = Depends(get_db)):
    if _live_autorenew(db, principal.tenant_id):
        raise HTTPException(409, "Auto-renew is already on. Cancel it first to change the plan.")
    yearly = body.billing_cycle == "yearly"
    amount = _renewal_amount(db, principal.tenant_id, yearly)
    sub = _latest_subscription(db, principal.tenant_id)
    payload = {"plan_id": _razorpay_plan(db, body.billing_cycle, amount), "total_count": 10 if yearly else 120, "customer_notify": 1,
               "notes": {"tenant_id": str(principal.tenant_id)}}
    if sub and sub.status in ("trial", "active") and sub.ends_at and sub.ends_at > now_utc() + timedelta(hours=1):
        payload["start_at"] = int(sub.ends_at.timestamp())  # the first charge happens when the trial or paid period ends
    created = razorpay.call("POST", "/subscriptions", json=payload)
    for old in db.scalars(select(AutoRenewal).where(AutoRenewal.tenant_id == principal.tenant_id, AutoRenewal.status == "created")):
        old.status = "cancelled"
    db.add(AutoRenewal(tenant_id=principal.tenant_id, razorpay_subscription_id=created["id"], billing_cycle=body.billing_cycle, amount_paise=amount))
    db.flush()
    user = db.get(User, principal.user_id)
    return {"key_id": razorpay.settings.razorpay_key_id, "subscription_id": created["id"], "email": user.email if user else None,
            "description": f"RestoIQ POS {body.billing_cycle} auto-renew", "amount": amount, "first_charge_at": payload.get("start_at")}


@router.post("/autorenew/verify")
def verify_autorenew(body: AutoRenewVerify, background: BackgroundTasks, principal: Principal = OWNER, db: Session = Depends(get_db)):
    if not (SUB_ID.match(body.razorpay_subscription_id) and PAYMENT_ID.match(body.razorpay_payment_id)):
        raise HTTPException(422, "Invalid details")
    ar = db.scalar(select(AutoRenewal).where(AutoRenewal.tenant_id == principal.tenant_id, AutoRenewal.razorpay_subscription_id == body.razorpay_subscription_id))
    if not ar:
        raise HTTPException(404, "Auto-renew not found")
    if not razorpay.subscription_signature_ok(body.razorpay_payment_id, body.razorpay_subscription_id, body.razorpay_signature):
        raise HTTPException(400, "Invalid signature")
    remote = razorpay.call("GET", f"/subscriptions/{ar.razorpay_subscription_id}")
    if remote.get("status") in ("authenticated", "active") and ar.status in ("created", "authenticated"):
        ar.status = remote["status"]
    if remote.get("status") == "active":
        payment = razorpay.call("GET", f"/payments/{body.razorpay_payment_id}")
        if payment.get("status") == "captured" and payment.get("amount") == ar.amount_paise and settle_charge(db, principal.tenant_id, ar, body.razorpay_payment_id, ar.amount_paise):
            inv = db.scalar(select(PaymentOrder.invoice_id).where(PaymentOrder.razorpay_order_id == f"sub_{body.razorpay_payment_id}"[:40]))
            if inv:
                _queue_receipt(db, background, inv, principal.tenant_id)
    audit(db, principal, "autorenew_started", "autorenewal", ar.id, {"cycle": ar.billing_cycle, "amount_paise": ar.amount_paise})
    return {"status": ar.status, "subscription": subscription_state(db, principal.tenant_id)}


@router.post("/autorenew/cancel")
def cancel_autorenew(principal: Principal = OWNER, db: Session = Depends(get_db)):
    ar = _live_autorenew(db, principal.tenant_id)
    if not ar:
        raise HTTPException(404, "Auto-renew is not on")
    razorpay.call("POST", f"/subscriptions/{ar.razorpay_subscription_id}/cancel", json={"cancel_at_cycle_end": 0})
    ar.status = "cancelled"
    audit(db, principal, "autorenew_cancelled", "autorenewal", ar.id, {})
    return {"status": "cancelled"}


def handle_subscription_event(db: Session, background: BackgroundTasks, event: dict) -> None:
    payload = event.get("payload", {})
    remote = (payload.get("subscription") or {}).get("entity") or {}
    sub_id = remote.get("id")
    tenant_id = int((remote.get("notes") or {}).get("tenant_id", 0) or 0)
    if not (sub_id and SUB_ID.match(sub_id) and tenant_id):
        return
    set_tenant_context(db, tenant_id)
    ar = db.scalar(select(AutoRenewal).where(AutoRenewal.tenant_id == tenant_id, AutoRenewal.razorpay_subscription_id == sub_id))
    if not ar:
        return
    name = event.get("event")
    if name == "subscription.charged":
        payment = (payload.get("payment") or {}).get("entity") or {}
        pid = payment.get("id")
        if pid and PAYMENT_ID.match(pid) and payment.get("amount") == ar.amount_paise and settle_charge(db, tenant_id, ar, pid, ar.amount_paise):
            ar.status = "active"
            po = db.scalar(select(PaymentOrder.invoice_id).where(PaymentOrder.razorpay_order_id == f"sub_{pid}"[:40]))
            if po:
                _queue_receipt(db, background, po, tenant_id)
    elif name in ("subscription.authenticated", "subscription.activated"):
        if ar.status in ("created", "authenticated"):
            ar.status = "authenticated" if name.endswith("authenticated") else "active"
    elif name in ("subscription.halted", "subscription.cancelled", "subscription.completed"):
        ar.status = name.split(".")[1]
