"""Running-order changes: add items as a new KOT, cancel items."""
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai_operations.service import create_staff_task
from app.auth.dependencies import Principal, require_roles
from app.core.audit import audit
from app.core.events import add_business_event
from app.db import get_db
from app.models import DiningTable, MenuItem, OperationalEvent, OrderItem, Payment, RestaurantOrder
from app.pos.router import MANAGERS, ORDER_TAKER_ROLES
from app.pos.schemas import OrderLineInput
from app.pos.service import apply_charges, load_options, money, price_line, order_or_404, order_to_dict, outlet_or_404

from app.integrations.providers.urbanpiper import publish_order_status  # noqa: E402

router = APIRouter(prefix="/api/v1", tags=["pos"])
CLOSED = {"paid", "completed", "cancelled", "refunded"}


class AddItemsInput(BaseModel):
    items: list[OrderLineInput] = Field(min_length=1, max_length=100)


class CancelItemInput(BaseModel):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=300)]


class ChargesInput(BaseModel):
    discount_type: Literal["percent", "fixed"] | None = None
    discount_value: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    discount_reason: str | None = Field(default=None, max_length=300)
    waive_service_charge: bool = False
    tip: Decimal = Field(default=Decimal("0"), ge=0, le=100000, decimal_places=2)


def _recalculate(order: RestaurantOrder, outlet) -> None:
    try:
        apply_charges(order, outlet)
    except ValueError as exc:
        # A fixed discount larger than the remaining items cannot stay applied.
        raise HTTPException(409, f"{exc}. Adjust the discount first") from exc


def _paid(db: Session, tenant_id: int, order_id: int) -> Decimal:
    return Decimal(db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).where(
        Payment.order_id == order_id, Payment.tenant_id == tenant_id, Payment.status == "recorded")) or 0)


@router.post("/orders/{order_id}/items", status_code=201)
def add_items(
    order_id: int, body: AddItemsInput, db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles(*ORDER_TAKER_ROLES)),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    order = order_or_404(db, principal, order_id, for_update=True)
    event_key = None
    if idempotency_key:
        if len(idempotency_key) > 120:
            raise HTTPException(422, "Idempotency-Key must be at most 120 characters")
        event_key = f"order:{order.id}:kot-request:{idempotency_key}"
        # The order row is locked, so a concurrent retry waits here and then sees the first KOT.
        if db.scalar(select(OperationalEvent.id).where(
            OperationalEvent.tenant_id == principal.tenant_id, OperationalEvent.idempotency_key == event_key)):
            return order_to_dict(order)
    outlet = outlet_or_404(db, principal, order.restaurant_id)
    if order.status in CLOSED:
        raise HTTPException(409, f"Cannot add items to a {order.status} order")
    ids = {line.menu_item_id for line in body.items}
    menu = {m.id: m for m in db.scalars(select(MenuItem).where(
        MenuItem.id.in_(ids), MenuItem.restaurant_id == order.restaurant_id,
        MenuItem.tenant_id == principal.tenant_id, MenuItem.active.is_(True)))}
    if ids != set(menu):
        raise HTTPException(422, "One or more menu items are missing or unavailable")
    composition = (outlet.tax_config or {}).get("gst_scheme") == "composition"
    kot_no = max((i.kot_no for i in order.items), default=0) + 1
    options = load_options(db, principal.tenant_id, set(menu))
    for line in body.items:
        item = menu[line.menu_item_id]
        rate = Decimal("0") if composition else item.tax_rate
        unit, name, variant_name, addons = price_line(item, options[item.id], line.variant_id, line.addon_ids)
        base = money(unit * line.quantity)
        order.items.append(OrderItem(
            tenant_id=principal.tenant_id, menu_item_id=item.id, item_name=name, quantity=line.quantity,
            unit_price=unit, tax_rate=rate, line_total=base + money(base * rate / Decimal("100")),
            notes=line.notes, kot_no=kot_no, status="active", variant_name=variant_name, addons=addons or None,
        ))
    _recalculate(order, outlet)
    # The kitchen must see the new KOT again, and a requested bill is no longer final.
    if order.status not in {"submitted", "accepted", "preparing"}:
        order.status = "submitted"
    table = db.get(DiningTable, order.table_id) if order.table_id else None
    if table and table.tenant_id == principal.tenant_id and table.status == "BILLING":
        table.status = "OCCUPIED"
    db.flush()
    db.add(add_business_event(
        db, principal.tenant_id, order.restaurant_id, "KOT_ADDED", "native_pos",
        order_id=order.id, table_id=order.table_id,
        payload={"order_number": order.order_number, "kot_no": kot_no, "items": len(body.items)},
        idempotency_key=event_key or f"order:{order.id}:kot:{kot_no}",
    ))
    create_staff_task(
        db, principal, order.restaurant_id, "prepare_order", "kitchen",
        f"Prepare KOT {kot_no} of order {order.order_number}", table_id=order.table_id, order_id=order.id,
    )
    audit(db, principal, "order_items_added", "order", order.id, {"kot_no": kot_no})
    return order_to_dict(order)


@router.post("/orders/{order_id}/items/{item_id}/cancel")
def cancel_item(
    order_id: int, item_id: int, body: CancelItemInput, db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles(*MANAGERS, "cashier")),
):
    order = order_or_404(db, principal, order_id, for_update=True)
    outlet = outlet_or_404(db, principal, order.restaurant_id)
    if order.status in CLOSED:
        raise HTTPException(409, f"Cannot change a {order.status} order")
    item = next((i for i in order.items if i.id == item_id), None)
    if not item:
        raise HTTPException(404, "Order item not found")
    if item.status != "active":
        raise HTTPException(409, "Item is already cancelled")
    item.status, item.cancel_reason = "cancelled", body.reason
    _recalculate(order, outlet)
    if _paid(db, principal.tenant_id, order.id) > money(order.total + order.tip):
        raise HTTPException(409, "Payments already recorded exceed the new total; refund first")
    if not order.active_items:
        order.status = "cancelled"
        publish_order_status(db, order, "Cancelled", "item_out_of_stock" if "stock" in (body.reason or "").lower() else "unspecified", body.reason)
        table = db.get(DiningTable, order.table_id) if order.table_id else None
        other_open = order.table_id and db.scalar(select(func.count()).select_from(RestaurantOrder).where(
            RestaurantOrder.tenant_id == principal.tenant_id, RestaurantOrder.table_id == order.table_id,
            RestaurantOrder.id != order.id, RestaurantOrder.status.notin_(tuple(CLOSED))))
        if table and table.tenant_id == principal.tenant_id and table.status in {"OCCUPIED", "BILLING"} and not other_open:
            table.status = "FREE"
    db.add(add_business_event(
        db, principal.tenant_id, order.restaurant_id, "ITEM_CANCELLED", "native_pos",
        order_id=order.id, table_id=order.table_id,
        payload={"item": item.item_name, "quantity": item.quantity, "reason": body.reason},
        idempotency_key=f"order:{order.id}:item:{item.id}:cancelled",
    ))
    audit(db, principal, "order_item_cancelled", "order", order.id, {"item_id": item.id, "reason": body.reason})
    return order_to_dict(order)


@router.put("/orders/{order_id}/charges")
def set_charges(
    order_id: int, body: ChargesInput, db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles(*MANAGERS, "cashier")),
):
    """Set discount (with a reason), service-charge waiver and tip. The bill is recalculated."""
    order = order_or_404(db, principal, order_id, for_update=True)
    outlet = outlet_or_404(db, principal, order.restaurant_id)
    if order.status in CLOSED:
        raise HTTPException(409, f"Cannot change a {order.status} order")
    has_discount = body.discount_type is not None and body.discount_value > 0
    reason = (body.discount_reason or "").strip()
    if has_discount and len(reason) < 3:
        raise HTTPException(422, "A reason is required for a discount")
    order.discount_type = body.discount_type if has_discount else None
    order.discount_value = body.discount_value if has_discount else Decimal("0")
    order.discount_reason = reason if has_discount else None
    order.service_charge_waived = body.waive_service_charge
    order.tip = money(body.tip)
    try:
        apply_charges(order, outlet)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if _paid(db, principal.tenant_id, order.id) > money(order.total + order.tip):
        raise HTTPException(409, "Payments already recorded exceed the new payable amount; refund first")
    audit(db, principal, "order_charges_changed", "order", order.id, {
        "discount_type": order.discount_type, "discount_value": str(order.discount_value),
        "reason": order.discount_reason, "service_waived": order.service_charge_waived, "tip": str(order.tip),
    })
    return order_to_dict(order)
