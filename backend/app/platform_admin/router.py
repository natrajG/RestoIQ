from datetime import date, datetime, time, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import Principal, require_roles
from app.core.audit import audit
from app.core.subscriptions import subscription_state, MONTHLY_PRICE_INR, PLAN_DEFINITIONS, YEARLY_PRICE_INR, _latest_subscription, current_plan_name
from app.db import get_db, set_tenant_context
from app.models import (
    Invoice, PlanPrice, ReminderLog, Restaurant, Subscription, SubscriptionPlan, Tenant, TenantProfile, User, now_utc,
)

router = APIRouter(prefix="/api/v1/platform", tags=["platform-admin"])
public_router = APIRouter(prefix="/api/v1/public", tags=["public"])
ADMIN = Depends(require_roles("platform_admin"))
DEFAULT_PRICES = {"RESTOIQ_POS": (Decimal(MONTHLY_PRICE_INR), Decimal(YEARLY_PRICE_INR))}
CENT = Decimal("0.01")


class PlanPriceUpdate(BaseModel):
    price_inr: Decimal = Field(ge=0, le=1_000_000, decimal_places=2)
    yearly_price_inr: Decimal = Field(ge=0, le=10_000_000, decimal_places=2)
    gst_percent: Decimal = Field(ge=0, le=100, decimal_places=2)


class SubscriptionAction(BaseModel):
    action: str = Field(pattern="^(extend_trial|activate)$")
    days: int = Field(default=7, ge=1, le=365)


class InvoiceCreate(BaseModel):
    tenant_id: int


class InvoiceUpdate(BaseModel):
    status: str = Field(pattern="^(paid|void|pending)$")


def _prices(db: Session) -> dict[str, PlanPrice]:
    rows = {p.plan_name: p for p in db.scalars(select(PlanPrice))}
    for name in PLAN_DEFINITIONS:
        if name not in rows:
            monthly, yearly = DEFAULT_PRICES.get(name, (Decimal("0"), Decimal("0")))
            rows[name] = PlanPrice(plan_name=name, price_inr=monthly, yearly_price_inr=yearly, gst_percent=Decimal("18"))
            db.add(rows[name])
    db.flush()
    return rows


def _price_json(p: PlanPrice) -> dict:
    return {"plan_name": p.plan_name, "price_inr": float(p.price_inr), "yearly_price_inr": float(p.yearly_price_inr), "gst_percent": float(p.gst_percent),
            "description": PLAN_DEFINITIONS.get(p.plan_name, {}).get("description", "")}


def _invoice_json(i: Invoice, tenant_name: str | None = None) -> dict:
    return {"id": i.id, "number": i.number, "tenant_id": i.tenant_id, "tenant_name": tenant_name,
            "plan_name": i.plan_name, "outlets": i.outlets, "subtotal": float(i.subtotal), "gst": float(i.gst),
            "total": float(i.total), "status": i.status, "period_start": i.period_start.isoformat(),
            "period_end": i.period_end.isoformat(), "created_at": i.created_at, "paid_at": i.paid_at}


def build_invoice(db: Session, tenant_id: int, yearly: bool, period_start: date) -> Invoice:
    """Create a pending subscription invoice: unit price x outlets, plus GST."""
    plan = current_plan_name(db, tenant_id)
    price = _prices(db)[plan]
    outlets = max(db.scalar(select(func.count()).select_from(Restaurant).where(Restaurant.tenant_id == tenant_id)) or 0, 1)
    subtotal = ((price.yearly_price_inr if yearly else price.price_inr) * outlets).quantize(CENT, ROUND_HALF_UP)
    gst = (subtotal * price.gst_percent / 100).quantize(CENT, ROUND_HALF_UP)
    inv = Invoice(tenant_id=tenant_id, number="PENDING", plan_name=plan, outlets=outlets, subtotal=subtotal,
                  gst=gst, total=subtotal + gst, status="pending", period_start=period_start,
                  period_end=period_start + timedelta(days=365 if yearly else 30))
    db.add(inv)
    db.flush()
    inv.number = f"INV-{date.today():%Y%m}-{inv.id:05d}"
    return inv


def _tenants(db: Session) -> list[Tenant]:
    return list(db.scalars(select(Tenant).order_by(Tenant.id)))


@router.get("/restaurants")
def restaurants(principal: Principal = ADMIN, db: Session = Depends(get_db)):
    rows = []
    for t in _tenants(db):
        set_tenant_context(db, t.id)
        profile = db.scalar(select(TenantProfile).where(TenantProfile.tenant_id == t.id))
        sub = db.scalar(select(Subscription).where(Subscription.tenant_id == t.id)
                        .order_by(Subscription.starts_at.desc(), Subscription.id.desc()))
        owner = db.scalar(select(User).where(User.tenant_id == t.id, User.role == "owner").order_by(User.id))
        outlets = db.scalar(select(func.count()).select_from(Restaurant).where(Restaurant.tenant_id == t.id)) or 0
        staff = db.scalar(select(func.count()).select_from(User).where(User.tenant_id == t.id)) or 0
        due = db.scalar(select(func.coalesce(func.sum(Invoice.total), 0)).where(
            Invoice.tenant_id == t.id, Invoice.status == "pending")) or 0
        paid_total = db.scalar(select(func.coalesce(func.sum(Invoice.total), 0)).where(
            Invoice.tenant_id == t.id, Invoice.status == "paid")) or 0
        last_paid = db.scalar(select(func.max(Invoice.paid_at)).where(Invoice.tenant_id == t.id, Invoice.status == "paid"))
        rem = db.execute(select(func.count(), func.max(ReminderLog.created_at)).where(ReminderLog.tenant_id == t.id)).one()
        state = subscription_state(db, t.id) if sub else {}
        rows.append({
            "paid_total": float(paid_total), "last_paid_at": last_paid, "days_left": state.get("days_left"),
            "plan_ends_at": sub.ends_at if sub else None,
            "reminders_sent": rem[0], "last_reminder_at": rem[1],
            "id": t.id, "name": t.name, "created_at": t.created_at,
            "owner_email": owner.email if owner else None,
            "owner_name": profile.owner_name if profile else None,
            "mobile": profile.mobile if profile else None,
            "city": profile.city if profile else None,
            "plan_name": current_plan_name(db, t.id),
            "subscription_status": subscription_state(db, t.id)["status"] if sub else "none",
            "trial_ends_at": (sub.ends_at if sub and sub.ends_at else (profile.trial_ends_at if profile else None)),
            "billing_cycle": sub.billing_cycle if sub else None, "outlets": outlets, "users": staff, "amount_due": float(due),
        })
    return {"restaurants": rows}


@router.get("/plans")
def plans(principal: Principal = ADMIN, db: Session = Depends(get_db)):
    prices = _prices(db)
    db.commit()
    return {"plans": [_price_json(prices[n]) for n in PLAN_DEFINITIONS]}


@router.put("/plans/{plan_name}")
def update_plan(plan_name: str, body: PlanPriceUpdate, principal: Principal = ADMIN, db: Session = Depends(get_db)):
    if plan_name not in PLAN_DEFINITIONS:
        raise HTTPException(404, "Unknown plan")
    price = _prices(db)[plan_name]
    old = float(price.price_inr)
    price.price_inr, price.yearly_price_inr = body.price_inr, body.yearly_price_inr
    price.gst_percent, price.updated_at = body.gst_percent, now_utc()
    audit(db, principal, "plan_price_updated", "plan", plan_name, {"old": old, "new": float(body.price_inr)})
    db.commit()
    return _price_json(price)


@router.post("/restaurants/{tenant_id}/remind")
def remind_restaurant(tenant_id: int, principal: Principal = ADMIN, db: Session = Depends(get_db)):
    from app.core import email_templates, mailer
    if not db.get(Tenant, tenant_id):
        raise HTTPException(404, "Restaurant not found")
    set_tenant_context(db, tenant_id)
    state = subscription_state(db, tenant_id)
    owner = db.scalar(select(User).where(User.tenant_id == tenant_id, User.role == "owner", User.is_active.is_(True)).order_by(User.id))
    if not owner:
        raise HTTPException(409, "This restaurant has no active owner to email")
    days = state.get("days_left")
    status = mailer.send_safe(owner.email, *email_templates.reminder(owner.full_name or "there", max(days or 0, 0), state.get("status") == "trial", state.get("status") in ("grace", "expired")))
    db.add(ReminderLog(tenant_id=tenant_id, kind="manual", days_left=days, to_email=owner.email, status=status))
    db.commit()
    if status == "not_configured":
        raise HTTPException(503, "Email is not configured on the server (set RESEND_API_KEY / MAIL_FROM)")
    if status == "failed":
        raise HTTPException(502, "The email could not be sent; see the reminder log")
    return {"sent_to": owner.email}


@router.get("/reminders")
def reminders(principal: Principal = ADMIN, db: Session = Depends(get_db)):
    names = {t.id: t.name for t in _tenants(db)}
    rows = db.scalars(select(ReminderLog).order_by(ReminderLog.id.desc()).limit(200))
    return {"reminders": [{"id": r.id, "tenant_id": r.tenant_id, "restaurant": names.get(r.tenant_id), "kind": r.kind,
                           "days_left": r.days_left, "to_email": r.to_email, "status": r.status, "created_at": r.created_at} for r in rows]}


@router.get("/invoices")
def invoices(principal: Principal = ADMIN, db: Session = Depends(get_db)):
    out = []
    for t in _tenants(db):
        set_tenant_context(db, t.id)
        out += [_invoice_json(i, t.name) for i in db.scalars(select(Invoice).where(Invoice.tenant_id == t.id))]
    out.sort(key=lambda i: i["id"], reverse=True)
    return {"invoices": out, "totals": {
        "pending": round(sum(i["total"] for i in out if i["status"] == "pending"), 2),
        "paid": round(sum(i["total"] for i in out if i["status"] == "paid"), 2)}}


@router.post("/invoices", status_code=201)
def create_invoice(body: InvoiceCreate, principal: Principal = ADMIN, db: Session = Depends(get_db)):
    tenant = db.get(Tenant, body.tenant_id)
    if not tenant:
        raise HTTPException(404, "Restaurant not found")
    set_tenant_context(db, tenant.id)
    sub = db.scalar(select(Subscription).where(Subscription.tenant_id == tenant.id)
                    .order_by(Subscription.starts_at.desc(), Subscription.id.desc()))
    if sub and sub.status == "trial" and sub.ends_at and sub.ends_at > now_utc():
        raise HTTPException(409, f"Free trial runs until {sub.ends_at.date().isoformat()}; no invoice yet")
    yearly = bool(sub and sub.billing_cycle == "yearly")
    inv = build_invoice(db, tenant.id, yearly, date.today())
    audit(db, Principal(principal.user_id, tenant.id, principal.role, principal.email), "invoice_created", "invoice", inv.id, {})
    db.commit()
    return _invoice_json(inv, tenant.name)


@router.patch("/invoices/{invoice_id}")
def update_invoice(invoice_id: int, body: InvoiceUpdate, tenant_id: int, principal: Principal = ADMIN,
                   db: Session = Depends(get_db)):
    set_tenant_context(db, tenant_id)
    inv = db.scalar(select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id))
    if not inv:
        raise HTTPException(404, "Invoice not found")
    inv.status = body.status
    inv.paid_at = now_utc() if body.status == "paid" else None
    if body.status == "paid":
        sub = _latest_subscription(db, tenant_id)
        if sub and inv.period_end:
            sub.status = "active"
            sub.billing_cycle = "yearly" if (inv.period_end - inv.period_start).days > 60 else "monthly"
            sub.ends_at = datetime.combine(inv.period_end, time(23, 59, 59), tzinfo=timezone.utc)
    db.commit()
    return _invoice_json(inv)


@router.post("/restaurants/{tenant_id}/subscription")
def change_subscription(tenant_id: int, body: SubscriptionAction, principal: Principal = ADMIN, db: Session = Depends(get_db)):
    if not db.get(Tenant, tenant_id):
        raise HTTPException(404, "Restaurant not found")
    set_tenant_context(db, tenant_id)
    sub = _latest_subscription(db, tenant_id)
    if not sub:
        raise HTTPException(409, "Restaurant has no subscription")
    if body.action == "activate":
        sub.status, sub.ends_at = "active", None
    else:
        base = max(sub.ends_at or now_utc(), now_utc())
        sub.status, sub.ends_at = "trial", base + timedelta(days=body.days)
    audit(db, Principal(principal.user_id, tenant_id, principal.role, principal.email),
          "subscription_changed", "tenant", tenant_id, {"action": body.action, "days": body.days})
    db.commit()
    return {"status": sub.status, "ends_at": sub.ends_at}


@public_router.get("/plans")
def public_plans(db: Session = Depends(get_db)):
    prices = _prices(db)
    return {"plans": {n: {"price_inr": float(p.price_inr), "yearly_price_inr": float(p.yearly_price_inr), "gst_percent": float(p.gst_percent)} for n, p in prices.items() if n in PLAN_DEFINITIONS}}
