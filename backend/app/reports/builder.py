"""Weekly (7 days) and monthly (30 days) owner reports from recorded data only."""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DiningTable, Observation, Restaurant, StaffTask
from app.reports.insights import sales_insights

PERIOD_DAYS = {"weekly": 7, "monthly": 30}


def _pct(current: Decimal | int, previous: Decimal | int) -> float | None:
    return round(float((Decimal(current) - Decimal(previous)) / Decimal(previous) * 100), 1) if previous else None


def _occupancy(db: Session, tenant_id: int, outlet: Restaurant, start: datetime, end: datetime) -> dict:
    names = {t.id: t.name for t in db.scalars(select(DiningTable).where(
        DiningTable.tenant_id == tenant_id, DiningTable.restaurant_id == outlet.id))}
    rows = db.execute(select(Observation.table_id, Observation.observation_type, Observation.created_at).where(
        Observation.tenant_id == tenant_id, Observation.restaurant_id == outlet.id,
        Observation.observation_type.in_(("TABLE_OCCUPIED", "TABLE_FREE", "TABLE_UNKNOWN")),
        Observation.created_at >= start - timedelta(days=1), Observation.created_at < end,
    ).order_by(Observation.id).limit(100000)).all()
    open_since: dict[int, datetime] = {}
    sessions: dict[int, list[float]] = defaultdict(list)
    for table_id, kind, at in rows:
        if table_id is None:
            continue
        if kind == "TABLE_OCCUPIED":
            open_since.setdefault(table_id, at)
        elif table_id in open_since:
            began = open_since.pop(table_id)
            if kind == "TABLE_FREE" and at >= start:
                sessions[table_id].append((at - began).total_seconds() / 60)
    per_table = [{"table": names.get(t, str(t)), "sessions": len(v), "occupied_hours": round(sum(v) / 60, 1),
                  "avg_minutes": round(sum(v) / len(v), 1)} for t, v in sessions.items()]
    per_table.sort(key=lambda r: -r["sessions"])
    all_s = [m for v in sessions.values() for m in v]
    return {
        "available": bool(rows), "validated": False,
        "sessions": len(all_s), "avg_dwell_minutes": round(sum(all_s) / len(all_s), 1) if all_s else None,
        "busiest_tables": per_table[:5], "quietest_tables": [r for r in reversed(per_table)][:5] if len(per_table) > 5 else [],
        "tables_never_occupied": sorted(n for t, n in names.items() if t not in sessions)[:20] if rows else [],
        "note": "From camera detection, which is not yet validated against real footage.",
    }


def _tasks(db: Session, tenant_id: int, outlet: Restaurant, start: datetime, end: datetime) -> dict:
    tasks = list(db.scalars(select(StaffTask).where(
        StaffTask.tenant_id == tenant_id, StaffTask.restaurant_id == outlet.id,
        StaffTask.created_at >= start, StaffTask.created_at < end)))
    by_type: dict[str, dict] = {}
    minutes: list[float] = []
    overdue = 0
    for t in tasks:
        row = by_type.setdefault(t.task_type, {"created": 0, "completed": 0})
        row["created"] += 1
        if t.completed_at:
            row["completed"] += 1
            minutes.append((t.completed_at - t.created_at).total_seconds() / 60)
            overdue += bool(t.due_at and t.completed_at > t.due_at)
        elif t.status not in ("cancelled",) and t.due_at and t.due_at < end:
            overdue += 1
    return {"created": len(tasks), "completed": len(minutes), "overdue": overdue,
            "avg_completion_minutes": round(sum(minutes) / len(minutes), 1) if minutes else None, "by_type": by_type}


def build_report(db: Session, tenant_id: int, outlet: Restaurant, period: str) -> dict:
    days = PERIOD_DAYS[period]
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    prev_start = start - timedelta(days=days)
    cur = sales_insights(db, tenant_id, outlet, days, end)
    prev = sales_insights(db, tenant_id, outlet, days, start)
    occupancy = _occupancy(db, tenant_id, outlet, start, end)
    tasks = _tasks(db, tenant_id, outlet, start, end)
    prev_tasks = _tasks(db, tenant_id, outlet, prev_start, start)

    highlights: list[str] = []
    cur_rev, prev_rev = Decimal(cur["revenue"]), Decimal(prev["revenue"])
    change = _pct(cur_rev, prev_rev)
    if cur["orders"]:
        text = f"Revenue {cur_rev:,.0f} {cur['currency']} from {cur['orders']} bills (average bill {Decimal(cur['average_bill']):,.0f})"
        highlights.append(text + (f", {change:+.1f}% vs the previous {days} days." if change is not None else "."))
        busy = max(cur["by_weekday"], key=lambda r: Decimal(r["revenue"]))
        quiet = min(cur["by_weekday"], key=lambda r: Decimal(r["revenue"]))
        if Decimal(busy["revenue"]) > 0:
            highlights.append(f"Best day: {busy['weekday']}; weakest day: {quiet['weekday']}.")
        if cur["by_hour"]:
            peak = max(cur["by_hour"], key=lambda r: Decimal(r["revenue"]))
            highlights.append(f"Peak hour: {peak['hour']:02d}:00-{(peak['hour'] + 1) % 24:02d}:00.")
        if cur["top_items"]:
            highlights.append(f"Most ordered: {', '.join(i['item'] for i in cur['top_items'][:3])}.")
        before = {i["item"]: i["quantity"] for i in prev["top_items"]}
        rising = [i["item"] for i in cur["top_items"] if before.get(i["item"], 0) and i["quantity"] >= before[i["item"]] * 1.25]
        if rising:
            highlights.append(f"Rising items: {', '.join(rising[:3])}.")
    else:
        highlights.append("No sales recorded in this period. Import or connect your POS to get revenue insights.")
    if occupancy["available"] and occupancy["sessions"]:
        highlights.append(f"Cameras saw {occupancy['sessions']} table sessions, average {occupancy['avg_dwell_minutes']} minutes (unvalidated).")
    if tasks["created"]:
        highlights.append(f"{tasks['completed']} of {tasks['created']} staff tasks completed"
                          + (f", average {tasks['avg_completion_minutes']} min" if tasks["avg_completion_minutes"] is not None else "")
                          + (f"; {tasks['overdue']} overdue." if tasks["overdue"] else "."))
    return {
        "period": period, "days": days, "outlet": outlet.name, "currency": outlet.currency,
        "from": start.isoformat(), "to": end.isoformat(),
        "sales": cur, "previous_sales": {"revenue": prev["revenue"], "orders": prev["orders"], "average_bill": prev["average_bill"]},
        "change": {"revenue_pct": change, "orders_pct": _pct(cur["orders"], prev["orders"])},
        "occupancy": occupancy, "tasks": tasks, "previous_tasks": {"created": prev_tasks["created"], "completed": prev_tasks["completed"]},
        "highlights": highlights,
    }
