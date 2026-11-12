"""Table cards with live order info, shift table, merge orders, KOT reprint."""
from datetime import datetime, timezone
from decimal import Decimal

from starlette.concurrency import run_in_threadpool
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import Principal, current_principal, require_roles
from app.core.audit import audit
from app.db import get_db
from app.models import DiningTable, OrderItem, Payment, RestaurantOrder
from app.pos.kot import CLOSED, _recalculate
from app.pos.router import ORDER_ROLES
from app.pos.service import money, next_bill_number, order_or_404, order_to_dict, outlet_or_404

router = APIRouter(prefix="/api/v1", tags=["pos"])


class ShiftInput(BaseModel):
    table_id: int


class MergeInput(BaseModel):
    into_order_id: int


class SplitLine(BaseModel):
    item_id: int
    quantity: int = Field(ge=1, le=999)


class SplitInput(BaseModel):
    lines: list[SplitLine] = Field(min_length=1, max_length=100)


def _table(db: Session, principal: Principal, table_id: int, outlet_id: int) -> DiningTable:
    t = db.scalar(select(DiningTable).where(
        DiningTable.id == table_id, DiningTable.tenant_id == principal.tenant_id, DiningTable.restaurant_id == outlet_id))
    if not t:
        raise HTTPException(404, "Table not found")
    return t


@router.get("/outlets/{outlet_id}/table-live")
def table_live(outlet_id: int, db: Session = Depends(get_db), principal: Principal = Depends(current_principal)):
    outlet_or_404(db, principal, outlet_id)
    orders = db.scalars(select(RestaurantOrder).where(
        RestaurantOrder.tenant_id == principal.tenant_id, RestaurantOrder.restaurant_id == outlet_id,
        RestaurantOrder.table_id.is_not(None), RestaurantOrder.status.notin_(tuple(CLOSED)),
    ).order_by(RestaurantOrder.created_at)).all()
    now = datetime.now(timezone.utc)
    live: dict = {}
    for o in orders:
        row = live.get(o.table_id)
        if row:  # split bills: one table, several open bills
            row["amount"] = str(money(Decimal(row["amount"]) + o.total))
            row["bills"] += 1
            continue
        live[o.table_id] = {
            "order_id": o.id, "order_number": o.order_number, "amount": str(money(o.total)), "waiter": o.staff_name,
            "covers": o.covers, "minutes": max(0, int((now - o.created_at).total_seconds() // 60)), "status": o.status,
            "bills": 1,
        }
    return live


@router.post("/orders/{order_id}/shift")
def shift_table(order_id: int, body: ShiftInput, db: Session = Depends(get_db),
                principal: Principal = Depends(require_roles(*ORDER_ROLES))):
    order = order_or_404(db, principal, order_id, for_update=True)
    outlet_or_404(db, principal, order.restaurant_id)
    if order.order_type != "dine_in" or not order.table_id:
        raise HTTPException(409, "Only a dine-in order can change table")
    if order.status in CLOSED:
        raise HTTPException(409, f"Cannot move a {order.status} order")
    if body.table_id == order.table_id:
        raise HTTPException(422, "Pick a different table")
    new = _table(db, principal, body.table_id, order.restaurant_id)
    if new.status not in {"FREE", "READY"}:
        raise HTTPException(409, f"{new.name} is not free ({new.status})")
    old = db.get(DiningTable, order.table_id)
    new.status = old.status if old.status in {"OCCUPIED", "BILLING"} else "OCCUPIED"
    old.status = "FREE"
    order.table_id = new.id
    audit(db, principal, "table_shifted", "order", order.id, {"from": old.name, "to": new.name})
    return order_to_dict(order)


@router.post("/orders/{order_id}/merge")
def merge_orders(order_id: int, body: MergeInput, db: Session = Depends(get_db),
                 principal: Principal = Depends(require_roles(*ORDER_ROLES))):
    if body.into_order_id == order_id:
        raise HTTPException(422, "Pick a different order")
    # Lock in a fixed id order so two waiters merging the same pair in opposite directions cannot deadlock.
    locked = {oid: order_or_404(db, principal, oid, for_update=True) for oid in sorted((order_id, body.into_order_id))}
    src, dst = locked[order_id], locked[body.into_order_id]
    outlet = outlet_or_404(db, principal, src.restaurant_id)
    if src.restaurant_id != dst.restaurant_id:
        raise HTTPException(422, "Orders belong to different outlets")
    for o in (src, dst):
        if o.status in CLOSED:
            raise HTTPException(409, f"Order {o.order_number} is {o.status}")
        paid = db.scalar(select(func.count()).select_from(Payment).where(
            Payment.order_id == o.id, Payment.tenant_id == principal.tenant_id, Payment.status == "recorded"))
        if paid:
            raise HTTPException(409, f"Order {o.order_number} already has a payment")
    offset = max((i.kot_no for i in dst.items), default=0)
    for item in list(src.items):
        item.kot_no += offset
        dst.items.append(item)
    src.status = "cancelled"
    src.remark = f"Merged into {dst.order_number}"
    if dst.status not in {"submitted", "accepted", "preparing"}:
        dst.status = "submitted"
    if src.table_id and src.table_id != dst.table_id:
        t = db.get(DiningTable, src.table_id)
        if t and t.tenant_id == principal.tenant_id:
            t.status = "FREE"
    db.flush()
    _recalculate(dst, outlet)
    audit(db, principal, "orders_merged", "order", dst.id, {"from": src.order_number})
    return order_to_dict(dst)


@router.post("/orders/{order_id}/split", status_code=201)
def split_order(order_id: int, body: SplitInput, db: Session = Depends(get_db),
                principal: Principal = Depends(require_roles(*ORDER_ROLES))):
    """Move chosen items (or part of a line's quantity) to a new bill on the same table, so guests pay separately."""
    order = order_or_404(db, principal, order_id, for_update=True)
    outlet = outlet_or_404(db, principal, order.restaurant_id)
    if order.status in CLOSED:
        raise HTTPException(409, f"Cannot split a {order.status} order")
    if db.scalar(select(func.count()).select_from(Payment).where(
            Payment.order_id == order.id, Payment.tenant_id == principal.tenant_id, Payment.status == "recorded")):
        raise HTTPException(409, "This bill already has a payment; refund it before splitting")
    wanted: dict[int, int] = {}
    for line in body.lines:
        if line.item_id in wanted:
            raise HTTPException(422, "Each item can appear only once")
        wanted[line.item_id] = line.quantity
    by_id = {i.id: i for i in order.active_items}
    moved: list[OrderItem] = []
    for item_id, qty in wanted.items():
        item = by_id.get(item_id)
        if not item:
            raise HTTPException(404, f"Item {item_id} is not an active item of this order")
        if qty > item.quantity:
            raise HTTPException(422, f"Only {item.quantity} of {item.item_name} on this bill")
        if qty == item.quantity:
            moved.append(item)
            continue
        item.quantity -= qty
        item.line_total = money(item.unit_price * item.quantity)
        moved.append(OrderItem(
            tenant_id=item.tenant_id, menu_item_id=item.menu_item_id, item_name=item.item_name, quantity=qty,
            unit_price=item.unit_price, tax_rate=item.tax_rate, line_total=money(item.unit_price * qty),
            notes=item.notes, kot_no=item.kot_no, complimentary=item.complimentary, status="active",
            variant_name=item.variant_name, addons=item.addons))
    kept = [i for i in order.active_items if i not in moved]
    if not kept:
        raise HTTPException(422, "Leave at least one item on the original bill")
    new = RestaurantOrder(
        tenant_id=principal.tenant_id, restaurant_id=order.restaurant_id, table_id=order.table_id,
        customer_id=order.customer_id, order_number=next_bill_number(db, principal.tenant_id, order.restaurant_id, outlet.timezone),
        order_type=order.order_type, contact_name=order.contact_name, contact_phone=order.contact_phone,
        delivery_address=order.delivery_address, status=order.status, source=order.source, covers=None,
        staff_name=order.staff_name, remark=f"Split from {order.order_number}",
        discount_type="percent" if order.discount_type == "percent" else None,
        discount_value=order.discount_value if order.discount_type == "percent" else Decimal("0"),
        discount_reason=order.discount_reason if order.discount_type == "percent" else None,
        service_charge_waived=order.service_charge_waived)
    db.add(new)
    db.flush()
    for item in moved:
        if item.id is None:
            item.order_id = new.id
            db.add(item)
        else:
            order.items.remove(item)
            item.order_id = new.id
            new.items.append(item)
    db.flush()
    db.refresh(order)
    db.refresh(new)
    _recalculate(order, outlet)
    _recalculate(new, outlet)
    audit(db, principal, "order_split", "order", order.id, {"new_order": new.order_number, "lines": len(moved)})
    return {"original": order_to_dict(order), "new": order_to_dict(new)}
