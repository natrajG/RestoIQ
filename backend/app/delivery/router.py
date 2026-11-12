"""Inbound delivery-aggregator orders (Swiggy, Zomato, ...) through a vendor-neutral webhook.

Swiggy and Zomato expose order APIs only to approved partners, usually via middleware such as UrbanPiper.
That middleware (or a small adapter) posts the canonical JSON documented in docs/DELIVERY_INTEGRATION.md.
"""
import hashlib
import json
import secrets
from decimal import Decimal, InvalidOperation

from starlette.concurrency import run_in_threadpool
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai_operations.service import create_staff_task
from app.auth.dependencies import Principal, require_roles
from app.core.audit import audit
from app.core.config import settings
from app.core.events import add_business_event
from app.core.security import decrypt_camera_url, encrypt_camera_url
from app.db import get_db, set_tenant_context
from app.models import (
    DeliveryChannel, DeliveryOrder, MenuItem, OrderItem, Payment, Restaurant, RestaurantOrder,
)
from app.delivery.adapters import PROVIDERS, get_adapter
from app.pos.service import apply_charges, customer_for_phone, money, next_bill_number

router = APIRouter(prefix="/api/v1", tags=["delivery"])
MANAGERS = ("owner", "manager", "admin")
MAX_BODY = 256 * 1024


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _dec(value, default: Decimal | None = None) -> Decimal | None:
    try:
        return money(Decimal(str(value)))
    except (InvalidOperation, TypeError, ValueError):
        return default


# ---- Management (owner/manager) ---------------------------------------------------------

class ChannelIn(BaseModel):
    provider: str
    label: str | None = Field(default=None, max_length=80)


def _public_base(request: Request) -> str:
    return str(request.base_url).rstrip("/")


def _channel_dict(c: DeliveryChannel) -> dict:
    return {"id": c.id, "restaurant_id": c.restaurant_id, "provider": c.provider, "label": c.label,
            "active": c.active, "created_at": c.created_at}


def _own_outlet(db: Session, principal: Principal, outlet_id: int) -> Restaurant:
    outlet = db.scalar(select(Restaurant).where(Restaurant.id == outlet_id, Restaurant.tenant_id == principal.tenant_id))
    if not outlet:
        raise HTTPException(404, "Outlet not found")
    return outlet


@router.get("/delivery/providers")
def list_providers(_: Principal = Depends(require_roles(*MANAGERS))):
    return [{"key": a.key, "label": a.label, "inbound_orders": a.inbound_orders, "outbound_sync": a.outbound_sync, "notes": a.notes}
            for a in PROVIDERS.values()]


@router.get("/outlets/{outlet_id}/delivery/channels")
def list_channels(outlet_id: int, db: Session = Depends(get_db), principal: Principal = Depends(require_roles(*MANAGERS))):
    _own_outlet(db, principal, outlet_id)
    rows = db.scalars(select(DeliveryChannel).where(
        DeliveryChannel.tenant_id == principal.tenant_id, DeliveryChannel.restaurant_id == outlet_id).order_by(DeliveryChannel.id))
    return [_channel_dict(c) for c in rows]


@router.post("/outlets/{outlet_id}/delivery/channels", status_code=201)
def create_channel(outlet_id: int, body: ChannelIn, request: Request, db: Session = Depends(get_db),
                   principal: Principal = Depends(require_roles(*MANAGERS))):
    """The URL and secret are shown once; only a hash of the token is stored."""
    _own_outlet(db, principal, outlet_id)
    if body.provider not in PROVIDERS:
        raise HTTPException(422, "Unsupported provider")
    token, secret = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    channel = DeliveryChannel(tenant_id=principal.tenant_id, restaurant_id=outlet_id, provider=body.provider,
                              label=body.label, token_hash=_hash(token), secret_ciphertext=encrypt_camera_url(secret))
    db.add(channel)
    db.flush()
    audit(db, principal, "delivery_channel_created", "delivery_channel", channel.id, {"provider": body.provider})
    return _channel_dict(channel) | {"webhook_url": f"{_public_base(request)}/api/v1/delivery/webhook/{token}", "secret": secret}


@router.post("/outlets/{outlet_id}/delivery/channels/{channel_id}/disable")
def disable_channel(outlet_id: int, channel_id: int, db: Session = Depends(get_db),
                    principal: Principal = Depends(require_roles(*MANAGERS))):
    channel = db.scalar(select(DeliveryChannel).where(
        DeliveryChannel.id == channel_id, DeliveryChannel.restaurant_id == outlet_id, DeliveryChannel.tenant_id == principal.tenant_id))
    if not channel:
        raise HTTPException(404, "Channel not found")
    channel.active = False
    audit(db, principal, "delivery_channel_disabled", "delivery_channel", channel.id)
    return _channel_dict(channel)


@router.get("/outlets/{outlet_id}/delivery/orders")
def list_delivery_orders(outlet_id: int, status: str | None = None, limit: int = 50, db: Session = Depends(get_db),
                         principal: Principal = Depends(require_roles(*MANAGERS, "cashier"))):
    _own_outlet(db, principal, outlet_id)
    stmt = select(DeliveryOrder, RestaurantOrder.order_number).outerjoin(RestaurantOrder, RestaurantOrder.id == DeliveryOrder.order_id).where(
        DeliveryOrder.tenant_id == principal.tenant_id, DeliveryOrder.restaurant_id == outlet_id)
    if status:
        stmt = stmt.where(DeliveryOrder.status == status)
    rows = db.execute(stmt.order_by(DeliveryOrder.created_at.desc()).limit(min(max(limit, 1), 200))).all()
    return [{"id": d.id, "provider": d.provider, "external_id": d.external_id, "status": d.status, "order_id": d.order_id,
             "order_number": num, "aggregator_total": str(d.aggregator_total) if d.aggregator_total is not None else None,
             "commission": str(d.commission), "total_mismatch": d.total_mismatch, "unmatched": d.unmatched or [],
             "created_at": d.created_at} for d, num in rows]


@router.get("/outlets/{outlet_id}/delivery/summary")
def delivery_summary(outlet_id: int, db: Session = Depends(get_db), principal: Principal = Depends(require_roles(*MANAGERS))):
    """Per-channel gross, commission and net so the owner sees margin by channel."""
    _own_outlet(db, principal, outlet_id)
    rows = db.execute(
        select(DeliveryOrder.provider, func.count(), func.coalesce(func.sum(RestaurantOrder.total), 0), func.coalesce(func.sum(DeliveryOrder.commission), 0))
        .join(RestaurantOrder, RestaurantOrder.id == DeliveryOrder.order_id)
        .where(DeliveryOrder.tenant_id == principal.tenant_id, DeliveryOrder.restaurant_id == outlet_id, DeliveryOrder.status == "created")
        .group_by(DeliveryOrder.provider)).all()
    pending = db.scalar(select(func.count()).select_from(DeliveryOrder).where(
        DeliveryOrder.tenant_id == principal.tenant_id, DeliveryOrder.restaurant_id == outlet_id, DeliveryOrder.status == "needs_mapping"))
    return {"needs_mapping": pending, "channels": [
        {"provider": p, "orders": n, "gross": str(money(Decimal(g))), "commission": str(money(Decimal(c))), "net": str(money(Decimal(g) - Decimal(c)))}
        for p, n, g, c in rows]}


class MapIn(BaseModel):
    mappings: dict[str, int] = Field(description="external item name or SKU -> menu_item_id")


@router.post("/outlets/{outlet_id}/delivery/orders/{delivery_id}/resolve")
def resolve_unmapped(outlet_id: int, delivery_id: int, body: MapIn, db: Session = Depends(get_db),
                     principal: Principal = Depends(require_roles(*MANAGERS))):
    """Staff map unknown aggregator items to menu items; the order is then created and sent to the kitchen."""
    d = db.scalar(select(DeliveryOrder).where(DeliveryOrder.id == delivery_id, DeliveryOrder.restaurant_id == outlet_id,
                                              DeliveryOrder.tenant_id == principal.tenant_id).with_for_update())
    if not d:
        raise HTTPException(404, "Delivery order not found")
    if d.status != "needs_mapping":
        raise HTTPException(409, f"Order is already {d.status}")
    ids = set(body.mappings.values())
    valid = set(db.scalars(select(MenuItem.id).where(MenuItem.id.in_(ids), MenuItem.restaurant_id == outlet_id,
                                                      MenuItem.tenant_id == principal.tenant_id, MenuItem.active.is_(True))))
    if ids - valid:
        raise HTTPException(422, "One or more menu items are missing or unavailable")
    lookup = {k.strip().lower(): v for k, v in body.mappings.items()}
    outlet = _own_outlet(db, principal, outlet_id)
    matched, unmatched = _match_items(db, outlet, d.raw.get("items") or [], extra=lookup)
    if unmatched:
        d.unmatched = unmatched
        raise HTTPException(422, f"Still unmatched: {', '.join(unmatched)}")
    _create_order(db, outlet, d, matched, Principal(principal.user_id, principal.tenant_id, "system", principal.email))
    audit(db, principal, "delivery_order_resolved", "delivery_order", d.id)
    return {"id": d.id, "status": d.status, "order_id": d.order_id}


# ---- Webhook ------------------------------------------------------------------------------

def _match_items(db: Session, outlet: Restaurant, items: list[dict], extra: dict[str, int] | None = None):
    menu = db.scalars(select(MenuItem).where(MenuItem.restaurant_id == outlet.id, MenuItem.tenant_id == outlet.tenant_id,
                                              MenuItem.active.is_(True))).all()
    by_sku = {m.sku.strip().lower(): m for m in menu}
    by_name = {m.name.strip().lower(): m for m in menu}
    by_id = {m.id: m for m in menu}
    matched, unmatched = [], []
    for it in items:
        sku, name = (it.get("sku") or "").strip().lower(), (it.get("name") or "").strip().lower()
        m = None
        for key in (sku, name):
            if key and extra and key in extra:
                m = by_id.get(extra[key])
        m = m or by_sku.get(sku) or by_name.get(name)
        if m:
            matched.append((m, int(it["quantity"]), _dec(it.get("unit_price")), it.get("name")))
        else:
            unmatched.append(it.get("name") or it.get("sku") or "?")
    return matched, unmatched


def _create_order(db: Session, outlet: Restaurant, d: DeliveryOrder, matched, actor: Principal) -> RestaurantOrder:
    raw = d.raw
    cust = raw.get("customer") or {}
    composition = (outlet.tax_config or {}).get("gst_scheme") == "composition"
    order = RestaurantOrder(
        tenant_id=d.tenant_id, restaurant_id=outlet.id, order_type="delivery", status="submitted", source=d.provider,
        order_number=next_bill_number(db, d.tenant_id, outlet.id, outlet.timezone),
        idempotency_key=f"delivery:{d.channel_id}:{d.external_id}",
        contact_name=(cust.get("name") or "").strip() or None, contact_phone=cust.get("phone"),
        delivery_address=(raw.get("delivery_address") or "").strip() or None,
        remark=(raw.get("notes") or f"{d.provider} #{d.external_id}")[:300], staff_name=d.provider.title(),
        service_charge_waived=True,
    )
    known = customer_for_phone(db, d.tenant_id, outlet.id, order.contact_phone, order.contact_name)
    order.customer_id = known.id if known else None
    for item, qty, price, ext_name in matched:
        unit = price if price is not None else item.price
        rate = Decimal("0") if composition else item.tax_rate
        base = money(unit * qty)
        order.items.append(OrderItem(tenant_id=d.tenant_id, menu_item_id=item.id, item_name=item.name, quantity=qty,
                                     unit_price=unit, tax_rate=rate, line_total=base + money(base * rate / Decimal("100")),
                                     status="active", notes=None if ext_name == item.name else f"{d.provider}: {ext_name}"))
    apply_charges(order, outlet)
    db.add(order)
    db.flush()
    if raw.get("payment", "prepaid") == "prepaid":
        db.add(Payment(tenant_id=d.tenant_id, order_id=order.id, method=d.provider, status="recorded", amount=order.total,
                       reference=d.external_id, idempotency_key=f"delivery:{d.id}"))
    d.order_id, d.status, d.unmatched = order.id, "created", None
    if d.aggregator_total is not None and abs(d.aggregator_total - order.total) > Decimal("1.00"):
        d.total_mismatch = True
    db.add(add_business_event(db, d.tenant_id, outlet.id, "ORDER_PLACED", d.provider, order_id=order.id,
                              payload={"order_number": order.order_number, "external_id": d.external_id},
                              idempotency_key=f"order:{order.id}:placed"))
    create_staff_task(db, actor, outlet.id, "prepare_order", "kitchen", f"Prepare {d.provider.title()} order {order.order_number}", order_id=order.id)
    return order


@router.post("/delivery/webhook/{token}")
async def delivery_webhook(token: str, request: Request, db: Session = Depends(get_db)):
    raw = await request.body()
    # Blocking DB work runs off the event loop so a row lock cannot freeze the whole API.
    return await run_in_threadpool(_delivery_webhook, token, request, raw, db)


def _delivery_webhook(token: str, request: Request, raw: bytes, db: Session):
    if len(raw) > MAX_BODY:
        raise HTTPException(413, "Payload too large")
    channel = db.scalar(select(DeliveryChannel).where(DeliveryChannel.token_hash == _hash(token)))
    if not channel or not channel.active:
        raise HTTPException(404, "Unknown channel")
    adapter = get_adapter(channel.provider)
    if not adapter.verify(raw, request.headers, decrypt_camera_url(channel.secret_ciphertext)):
        raise HTTPException(401, "Invalid signature")
    try:
        body = adapter.parse(json.loads(raw))
    except Exception as exc:
        raise HTTPException(422, "Invalid payload") from exc

    set_tenant_context(db, channel.tenant_id)
    outlet = db.get(Restaurant, channel.restaurant_id)
    existing = db.scalar(select(DeliveryOrder).where(DeliveryOrder.channel_id == channel.id,
                                                     DeliveryOrder.external_id == body.external_order_id).with_for_update())
    actor = Principal(0, channel.tenant_id, "system", channel.provider)

    if body.event == "order.cancelled":
        if not existing:
            raise HTTPException(404, "Order not found")
        order = db.get(RestaurantOrder, existing.order_id) if existing.order_id else None
        if order and order.status in {"completed", "paid"}:
            raise HTTPException(409, "Order is already completed")
        if order:
            order.status = "cancelled"
        existing.status = "cancelled"
        audit(db, actor, "delivery_order_cancelled", "delivery_order", existing.id)
        return {"status": "cancelled"}

    if existing:  # replay of the same order: acknowledge without creating anything new
        return {"status": existing.status, "order_id": existing.order_id, "duplicate": True}
    if not body.items:
        raise HTTPException(422, "Order has no items")

    d = DeliveryOrder(tenant_id=channel.tenant_id, restaurant_id=outlet.id, channel_id=channel.id, provider=channel.provider,
                      external_id=body.external_order_id, status="needs_mapping", aggregator_total=body.total,
                      commission=body.commission, raw=json.loads(raw))
    db.add(d)
    db.flush()
    matched, unmatched = _match_items(db, outlet, [i.model_dump(mode="json") for i in body.items])
    if unmatched:
        d.unmatched = unmatched
        create_staff_task(db, actor, outlet.id, "map_delivery_items", "manager",
                          f"{channel.provider.title()} order {d.external_id} has unknown items: {', '.join(unmatched)[:200]}")
        return {"status": "needs_mapping", "unmatched": unmatched}
    order = _create_order(db, outlet, d, matched, actor)
    return {"status": "created", "order_id": order.id, "order_number": order.order_number}
