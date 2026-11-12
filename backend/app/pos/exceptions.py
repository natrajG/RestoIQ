"""Exceptions report: voids, cancelled items, discounts, complimentary items and refunds, with who did them.
Built from the audit log, so it only covers actions recorded since those events were audited."""
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import Principal, require_roles
from app.db import get_db
from app.models import AuditLog, OrderItem, Payment, Refund, RestaurantOrder, User
from app.pos.service import money, outlet_or_404

router = APIRouter(prefix="/api/v1", tags=["pos"])
OWNERS = ("owner", "admin", "manager")
LABELS = {"order_voided": "Bill voided", "order_item_cancelled": "Item cancelled", "order_charges_changed": "Discount / charge change",
          "complimentary_set": "Complimentary", "refund_recorded": "Refund"}
WATCHED = (*LABELS, "payment_recorded")


@router.get("/outlets/{outlet_id}/reports/exceptions")
def exceptions(outlet_id: int, date_from: date | None = None, date_to: date | None = None, db: Session = Depends(get_db),
               principal: Principal = Depends(require_roles(*OWNERS))):
    outlet = outlet_or_404(db, principal, outlet_id)
    tz = ZoneInfo(outlet.timezone or "Asia/Kolkata")
    today = datetime.now(tz).date()
    d1, d2 = date_from or today, date_to or today
    if d2 < d1 or (d2 - d1).days > 92:
        raise HTTPException(422, "Pick a range of up to 92 days")
    start = datetime.combine(d1, time.min, tzinfo=tz)
    end = datetime.combine(d2 + timedelta(days=1), time.min, tzinfo=tz)
    tid = principal.tenant_id
    logs = db.scalars(select(AuditLog).where(
        AuditLog.tenant_id == tid, AuditLog.action.in_(WATCHED), AuditLog.created_at >= start, AuditLog.created_at < end,
    ).order_by(AuditLog.created_at.desc()).limit(5000)).all()

    def rid(x: AuditLog) -> int | None:
        return int(x.resource_id) if x.resource_id and x.resource_id.isdigit() else None

    refund_orders = dict(db.execute(select(Refund.id, Refund.order_id).where(
        Refund.tenant_id == tid, Refund.id.in_([rid(x) for x in logs if x.action == "refund_recorded" and rid(x)]))).all())
    payment_orders = dict(db.execute(select(Payment.id, Payment.order_id).where(
        Payment.tenant_id == tid, Payment.id.in_([rid(x) for x in logs if x.action == "payment_recorded" and rid(x)]))).all())

    def order_id(x: AuditLog) -> int | None:
        if x.action == "refund_recorded":
            return refund_orders.get(rid(x))
        if x.action == "payment_recorded":
            return payment_orders.get(rid(x))
        return rid(x)

    ids = {oid for x in logs if (oid := order_id(x))}
    orders = {o.id: o for o in db.scalars(select(RestaurantOrder).where(
        RestaurantOrder.tenant_id == tid, RestaurantOrder.restaurant_id == outlet_id, RestaurantOrder.id.in_(ids)))}
    items = {i.id: i for i in db.scalars(select(OrderItem).where(
        OrderItem.tenant_id == tid, OrderItem.order_id.in_(ids)))} if ids else {}
    users = {u.id: (u.full_name or u.email) for u in db.scalars(select(User).where(User.tenant_id == tid))}

    rows, staff = [], defaultdict(lambda: defaultdict(lambda: {"count": 0, "amount": Decimal("0")}))
    for x in logs:
        o = orders.get(order_id(x) or -1)
        if not o:
            continue  # other outlet or unknown order
        d = x.details or {}
        who = users.get(x.user_id, "System") if x.user_id else "System"
        if x.action == "payment_recorded":
            s = staff[who][f"paid_{d.get('method', 'other')}"]
            s["count"] += 1
            s["amount"] += Decimal(str(d.get("amount", 0)))
            continue
        amount, reason = None, d.get("reason")
        if x.action == "order_voided":
            amount = o.total
        elif x.action == "order_item_cancelled":
            it = items.get(d.get("item_id"))
            amount = money(it.unit_price * it.quantity) if it else None
        elif x.action == "order_charges_changed":
            if Decimal(str(d.get("discount_value") or 0)) <= 0 and not d.get("service_waived"):
                continue  # a tip or no-op change is not an exception
            kind = "%" if d.get("discount_type") == "percent" else "₹"
            reason = f"{d.get('discount_value')}{kind} off" + (f" - {reason}" if reason else "") + (" (service charge waived)" if d.get("service_waived") else "")
        elif x.action == "complimentary_set":
            if not d.get("items"):
                continue  # complimentary cleared
            amount = money(sum((i.unit_price * i.quantity for i in items.values() if i.order_id == o.id and i.complimentary), Decimal('0')))
        elif x.action == "refund_recorded":
            amount = Decimal(str(d.get("amount", 0)))
        s = staff[who][x.action]
        s["count"] += 1
        s["amount"] += Decimal(str(amount or 0))
        rows.append({"time": x.created_at, "staff": who, "type": x.action, "label": LABELS[x.action], "bill": o.order_number,
                     "bill_status": o.status, "amount": str(amount) if amount is not None else None, "reason": reason})
    return {
        "from": str(d1), "to": str(d2), "rows": rows[:500],
        "by_staff": [{"staff": w, "actions": {k: {"count": v["count"], "amount": str(money(v["amount"]))} for k, v in a.items()}}
                     for w, a in sorted(staff.items())],
        "labels": LABELS,
    }
