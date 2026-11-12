"""Sales analytics from the restaurant's own POS bills."""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import OrderItem, Restaurant, RestaurantOrder


def sales_insights(db: Session, tenant_id: int, outlet: Restaurant, days: int, until: datetime | None = None) -> dict:
    tz = ZoneInfo(outlet.timezone)
    until = until or datetime.now(timezone.utc)
    since_dt = until - timedelta(days=days)
    orders = list(db.scalars(select(RestaurantOrder).where(
        RestaurantOrder.tenant_id == tenant_id, RestaurantOrder.restaurant_id == outlet.id,
        RestaurantOrder.created_at >= since_dt, RestaurantOrder.created_at < until, RestaurantOrder.status != "cancelled")))
    by_day: dict[str, list] = defaultdict(lambda: [Decimal("0"), 0])
    by_weekday: dict[int, list] = defaultdict(lambda: [Decimal("0"), 0])
    by_hour: dict[int, list] = defaultdict(lambda: [Decimal("0"), 0])
    local_by_order = {}
    for order in orders:
        local = order.created_at.astimezone(tz)
        local_by_order[order.id] = local
        for bucket, key in ((by_day, local.date().isoformat()), (by_weekday, local.weekday()), (by_hour, local.hour)):
            bucket[key][0] += order.total
            bucket[key][1] += 1
    items: dict[str, list] = defaultdict(lambda: [0, Decimal("0")])
    item_weekday: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    if orders:
        for item in db.scalars(select(OrderItem).where(OrderItem.tenant_id == tenant_id, OrderItem.status == "active", OrderItem.order_id.in_(list(local_by_order)))):
            items[item.item_name][0] += item.quantity
            items[item.item_name][1] += item.line_total
            item_weekday[local_by_order[item.order_id].weekday()][item.item_name] += item.quantity
    revenue = sum((o.total for o in orders), Decimal("0"))
    names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return {
        "days": days, "currency": outlet.currency, "orders": len(orders), "revenue": str(revenue),
        "average_bill": str((revenue / len(orders)).quantize(Decimal("0.01"))) if orders else None,
        "by_day": [{"date": d, "revenue": str(v[0]), "orders": v[1]} for d, v in sorted(by_day.items())],
        "by_weekday": [{"weekday": names[d], "revenue": str(by_weekday[d][0]), "orders": by_weekday[d][1]} for d in range(7)],
        "by_hour": [{"hour": h, "revenue": str(v[0]), "orders": v[1]} for h, v in sorted(by_hour.items())],
        "top_items": [{"item": n, "quantity": v[0], "revenue": str(v[1])} for n, v in sorted(items.items(), key=lambda p: -p[1][0])[:15]],
        "top_items_by_weekday": [{"weekday": names[d], "items": [{"item": n, "quantity": q} for n, q in sorted(item_weekday[d].items(), key=lambda p: -p[1])[:3]]} for d in range(7)],
        "note": "Computed from your POS bills. Weekday/hour use the outlet time zone.",
    }
