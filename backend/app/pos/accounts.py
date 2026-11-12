"""Complimentary items, non-chargeable bills, voiding unpaid orders, and the sales summary report."""
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from typing_extensions import Annotated

from app.auth.dependencies import Principal, require_roles
from app.core.audit import audit
from app.db import get_db
from app.models import DiningTable, MenuCategory, MenuItem, OrderItem, Payment, Refund, RestaurantOrder
from app.pos.kot import CLOSED, _recalculate
from app.pos.router import MANAGERS
from app.pos.service import money, order_or_404, order_to_dict, outlet_or_404

from app.integrations.providers.urbanpiper import publish_order_status  # noqa: E402

router = APIRouter(prefix="/api/v1", tags=["pos"])
BILLERS = (*MANAGERS, "cashier")
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=300)]


class ComplimentaryInput(BaseModel):
    item_ids: list[int] = Field(max_length=100)
    reason: Reason | None = None


class VoidInput(BaseModel):
    reason: Reason


def _payments(db: Session, principal: Principal, order_id: int) -> int:
    return db.scalar(select(func.count()).select_from(Payment).where(
        Payment.order_id == order_id, Payment.tenant_id == principal.tenant_id, Payment.status == "recorded")) or 0


@router.put("/orders/{order_id}/complimentary")
def set_complimentary(order_id: int, body: ComplimentaryInput, db: Session = Depends(get_db),
                      principal: Principal = Depends(require_roles(*BILLERS))):
    """Replace the set of free items. If every item is free the bill is non-chargeable and closes at zero."""
    order = order_or_404(db, principal, order_id, for_update=True)
    outlet = outlet_or_404(db, principal, order.restaurant_id)
    if order.status in CLOSED:
        raise HTTPException(409, f"Cannot change a {order.status} order")
    if body.item_ids and not body.reason:
        raise HTTPException(422, "Give a reason for the complimentary items")
    if _payments(db, principal, order.id):
        raise HTTPException(409, "Payments are already recorded on this order")
    active = {i.id: i for i in order.active_items}
    if not set(body.item_ids) <= set(active):
        raise HTTPException(422, "Unknown item")
    for i in active.values():
        i.complimentary = i.id in body.item_ids
    order.complimentary_reason = body.reason if body.item_ids else None
    _recalculate(order, outlet)
    if body.item_ids and len(body.item_ids) == len(active) and order.total + order.tip == 0:
        order.status = "paid"
    audit(db, principal, "complimentary_set", "order", order.id, {"items": len(body.item_ids), "reason": body.reason})
    return order_to_dict(order)


@router.post("/orders/{order_id}/void")
def void_order(order_id: int, body: VoidInput, db: Session = Depends(get_db),
               principal: Principal = Depends(require_roles(*MANAGERS))):
    order = order_or_404(db, principal, order_id, for_update=True)
    if order.status in CLOSED:
        raise HTTPException(409, f"Order is already {order.status}")
    if _payments(db, principal, order.id):
        raise HTTPException(409, "Refund the payments before voiding (an advance counts as a payment)")
    order.status = "cancelled"
    order.remark = f"Voided: {body.reason}"
    if order.table_id:
        t = db.get(DiningTable, order.table_id)
        if t and t.tenant_id == principal.tenant_id and t.status in {"OCCUPIED", "BILLING"}:
            t.status = "FREE"
    publish_order_status(db, order, "Cancelled", "unspecified", body.reason[:150])
    audit(db, principal, "order_voided", "order", order.id, {"reason": body.reason})
    return order_to_dict(order)


@router.get("/outlets/{outlet_id}/reports/sales-summary")
def sales_summary(outlet_id: int, date_from: date | None = None, date_to: date | None = None, db: Session = Depends(get_db),
                  principal: Principal = Depends(require_roles(*BILLERS, "analyst"))):
    outlet = outlet_or_404(db, principal, outlet_id)
    tz = ZoneInfo(outlet.timezone or "Asia/Kolkata")
    today = datetime.now(tz).date()
    d1, d2 = date_from or today, date_to or today
    if d2 < d1 or (d2 - d1).days > 92:
        raise HTTPException(422, "Pick a range of up to 92 days")
    start = datetime.combine(d1, time.min, tzinfo=tz)
    end = datetime.combine(d2 + timedelta(days=1), time.min, tzinfo=tz)
    tid = principal.tenant_id
    base = (RestaurantOrder.tenant_id == tid, RestaurantOrder.restaurant_id == outlet_id,
            RestaurantOrder.created_at >= start, RestaurantOrder.created_at < end)
    sold = ("paid", "completed")
    t = db.execute(select(
        func.count(), func.coalesce(func.sum(RestaurantOrder.subtotal), 0), func.coalesce(func.sum(RestaurantOrder.discount_total), 0),
        func.coalesce(func.sum(RestaurantOrder.tax_total), 0), func.coalesce(func.sum(RestaurantOrder.service_charge), 0),
        func.coalesce(func.sum(RestaurantOrder.round_off), 0), func.coalesce(func.sum(RestaurantOrder.total), 0),
    ).where(*base, RestaurantOrder.status.in_(sold))).one()
    comp = db.scalar(select(func.coalesce(func.sum(OrderItem.quantity * OrderItem.unit_price), 0)).join(
        RestaurantOrder, RestaurantOrder.id == OrderItem.order_id).where(
        *base, RestaurantOrder.status.in_(sold), OrderItem.complimentary.is_(True), OrderItem.status == "active")) or 0
    pending = db.scalar(select(func.coalesce(func.sum(RestaurantOrder.total), 0)).where(
        *base, RestaurantOrder.status.notin_((*sold, "cancelled", "refunded")))) or 0
    by_method = db.execute(select(Payment.method, func.count(), func.coalesce(func.sum(Payment.amount), 0)).join(
        RestaurantOrder, RestaurantOrder.id == Payment.order_id).where(
        RestaurantOrder.tenant_id == tid, RestaurantOrder.restaurant_id == outlet_id, Payment.status == "recorded",
        Payment.created_at >= start, Payment.created_at < end).group_by(Payment.method).order_by(Payment.method)).all()
    refunds = db.scalar(select(func.coalesce(func.sum(Refund.amount), 0)).join(
        RestaurantOrder, RestaurantOrder.id == Refund.order_id).where(
        RestaurantOrder.tenant_id == tid, RestaurantOrder.restaurant_id == outlet_id, Refund.status == "recorded",
        Refund.created_at >= start, Refund.created_at < end)) or 0
    by_type = db.execute(select(RestaurantOrder.order_type, func.count(), func.coalesce(func.sum(RestaurantOrder.total), 0)).where(
        *base, RestaurantOrder.status.in_(sold)).group_by(RestaurantOrder.order_type)).all()
    group_rows = db.execute(select(MenuCategory.name, func.sum(OrderItem.quantity), func.sum(OrderItem.quantity * OrderItem.unit_price)).select_from(
        OrderItem).join(RestaurantOrder, RestaurantOrder.id == OrderItem.order_id).join(
        MenuItem, MenuItem.id == OrderItem.menu_item_id).outerjoin(MenuCategory, MenuCategory.id == MenuItem.category_id).where(
        *base, RestaurantOrder.status.in_(sold), OrderItem.status == "active", OrderItem.complimentary.is_(False)).group_by(
        MenuCategory.name).order_by(func.sum(OrderItem.quantity * OrderItem.unit_price).desc())).all()
    item_rows = db.execute(select(OrderItem.item_name, func.sum(OrderItem.quantity), func.sum(OrderItem.quantity * OrderItem.unit_price)).select_from(
        OrderItem).join(RestaurantOrder, RestaurantOrder.id == OrderItem.order_id).where(
        *base, RestaurantOrder.status.in_(sold), OrderItem.status == "active", OrderItem.complimentary.is_(False)).group_by(
        OrderItem.item_name).order_by(func.sum(OrderItem.quantity * OrderItem.unit_price).desc())).all()
    collected = sum((Decimal(a) for _, _, a in by_method), Decimal("0"))
    on_account = sum((Decimal(a) for m, _, a in by_method if m == "customer_account"), Decimal("0"))
    tips = db.scalar(select(func.coalesce(func.sum(RestaurantOrder.tip), 0)).where(*base, RestaurantOrder.status.in_(sold))) or 0
    expected = Decimal(t[6]) + Decimal(tips)
    net_collected = collected - Decimal(refunds)
    on_open = db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).join(
        RestaurantOrder, RestaurantOrder.id == Payment.order_id).where(
        RestaurantOrder.tenant_id == tid, RestaurantOrder.restaurant_id == outlet_id, Payment.status == "recorded",
        Payment.created_at >= start, Payment.created_at < end, RestaurantOrder.status.notin_(sold))) or 0
    return {
        "reconciliation": {
            "billed": str(money(expected)), "collected": str(money(collected)), "refunds": str(money(Decimal(refunds))),
            "net_collected": str(money(net_collected)), "on_customer_account": str(money(on_account)),
            "advance_on_open_bills": str(money(Decimal(on_open))),
            "pending_collection": str(money(Decimal(pending))),
            "difference": str(money(net_collected - Decimal(on_open) - expected)),
            "note": "Billed includes tips. Advances on open bills are shown separately. A remaining difference usually means payments and bills fall on different days or a refund.",
        },
        "by_item": [{"item": n, "quantity": int(q or 0), "amount": str(money(Decimal(a or 0)))} for n, q, a in item_rows],
        "from": d1.isoformat(), "to": d2.isoformat(), "bills": t[0], "subtotal": str(money(Decimal(t[1]))),
        "complimentary": str(money(Decimal(comp))), "discount": str(money(Decimal(t[2]))), "tax": str(money(Decimal(t[3]))),
        "service_charge": str(money(Decimal(t[4]))), "round_off": str(money(Decimal(t[5]))), "total_sale": str(money(Decimal(t[6]))),
        "pending_collection": str(money(Decimal(pending))), "refunds": str(money(Decimal(refunds))),
        "by_method": [{"method": m, "count": c, "amount": str(money(Decimal(a)))} for m, c, a in by_method],
        "by_type": [{"type": ty, "count": c, "amount": str(money(Decimal(a)))} for ty, c, a in by_type],
        "by_group": [{"group": g or "Uncategorised", "quantity": int(q or 0), "amount": str(money(Decimal(a or 0)))} for g, q, a in group_rows],
    }
