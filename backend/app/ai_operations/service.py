from collections import defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.auth.dependencies import Principal
from app.ai_operations.repository import MenuDemandPoint
from app.ai_operations.geometry import validate_table_polygon
from app.ai_operations.schemas import CameraRegionInput
from app.core.events import add_business_event
from app.models import StaffTask, now_utc

ROLE_ALIASES = {
    "cleaner": "cleaning",
    "server": "waiter",
}


def canonical_staff_role(role: str) -> str:
    return ROLE_ALIASES.get(role.lower(), role.lower())


def camera_regions_payload(regions: list[CameraRegionInput]) -> list[dict]:
    table_ids = [region.table_id for region in regions]
    if len(table_ids) != len(set(table_ids)):
        raise ValueError("A table can only have one zone per camera")
    for region in regions:
        validate_table_polygon(region.polygon)
    return [region.model_dump() for region in regions]


def create_staff_task(
    db: Session,
    principal: Principal,
    outlet_id: int,
    task_type: str,
    target_role: str,
    title: str,
    *,
    table_id: int | None = None,
    order_id: int | None = None,
    details: dict | None = None,
) -> StaffTask:
    task = StaffTask(
        tenant_id=principal.tenant_id,
        restaurant_id=outlet_id,
        table_id=table_id,
        order_id=order_id,
        task_type=task_type,
        target_role=canonical_staff_role(target_role),
        title=title,
        details=details or {},
        due_at=now_utc() + timedelta(minutes=5),
        created_by=principal.user_id or None,
    )
    db.add(task)
    db.flush()
    db.add(add_business_event(
        db, principal.tenant_id, outlet_id, "STAFF_TASK_CREATED", "operations",
        order_id=order_id, table_id=table_id,
        payload={"task_id": task.id, "task_type": task_type, "target_role": task.target_role},
        idempotency_key=f"staff-task:{task.id}:created",
    ))
    return task


def task_to_dict(task: StaffTask) -> dict:
    overdue = task.status not in {"completed", "cancelled"} and task.due_at is not None and task.due_at < now_utc()
    return {
        "id": task.id,
        "restaurant_id": task.restaurant_id,
        "table_id": task.table_id,
        "order_id": task.order_id,
        "task_type": task.task_type,
        "target_role": task.target_role,
        "assigned_employee_id": task.assigned_employee_id,
        "status": "overdue" if overdue and task.status == "pending" else task.status,
        "title": task.title,
        "details": task.details,
        "due_at": task.due_at,
        "acknowledged_at": task.acknowledged_at,
        "completed_at": task.completed_at,
    }


def meal_slot(local_time: datetime) -> str:
    hour = local_time.hour
    if 6 <= hour < 11:
        return "breakfast"
    if 11 <= hour < 16:
        return "lunch"
    if 16 <= hour < 19:
        return "snacks"
    if 19 <= hour < 23:
        return "dinner"
    return "late-night"


def menu_recommendations(
    demand_points: list[MenuDemandPoint],
    timezone_name: str,
    *,
    now_utc_dt: datetime | None = None,
    active_festival: str | None = None,
) -> list[dict]:
    if len(demand_points) < 20:
        return []
    current_utc = now_utc_dt or now_utc()
    current_local = current_utc.astimezone(ZoneInfo(timezone_name))
    current_slot = meal_slot(current_local)
    current_weekday = current_local.weekday()

    slot_day_counts: dict[str, int] = defaultdict(int)
    slot_counts: dict[str, int] = defaultdict(int)
    recent_counts: dict[str, int] = defaultdict(int)
    baseline_counts: dict[str, int] = defaultdict(int)
    recent_threshold = current_utc - timedelta(days=14)
    baseline_threshold = current_utc - timedelta(days=42)

    for point in demand_points:
        ordered_at = point.ordered_at
        if ordered_at.tzinfo is None:
            ordered_at = ordered_at.replace(tzinfo=ZoneInfo("UTC"))
        local = ordered_at.astimezone(ZoneInfo(timezone_name))
        slot = meal_slot(local)
        item = point.item_name
        quantity = max(point.quantity, 0)
        if slot == current_slot and local.weekday() == current_weekday:
            slot_day_counts[item] += quantity
        if slot == current_slot:
            slot_counts[item] += quantity
        if ordered_at >= recent_threshold:
            recent_counts[item] += quantity
        elif ordered_at >= baseline_threshold:
            baseline_counts[item] += quantity

    top_slot_day = sorted(slot_day_counts.items(), key=lambda pair: pair[1], reverse=True)
    top_slot = sorted(slot_counts.items(), key=lambda pair: pair[1], reverse=True)
    focus_items = top_slot_day[:3] if top_slot_day else top_slot[:3]
    if not focus_items:
        return []

    trending = []
    for item, recent in sorted(recent_counts.items(), key=lambda pair: pair[1], reverse=True):
        baseline = baseline_counts.get(item, 0)
        if recent < 6:
            continue
        if baseline == 0 and recent >= 10:
            trending.append((item, "new-demand"))
        elif baseline > 0 and recent >= int(baseline * 1.25):
            trending.append((item, "rising"))
        if len(trending) >= 3:
            break

    recommendation = {
        "title": "Optimize prep for current demand window",
        "evidence": {
            "analysis_window_days": 56,
            "day_of_week": current_local.strftime("%A"),
            "meal_window": current_slot,
            "top_items": [{"item": item, "ordered_quantity": quantity} for item, quantity in focus_items],
            "trend_watchlist": [{"item": item, "signal": signal} for item, signal in trending],
            "active_festival": active_festival,
        },
        "estimated_impact": None,
        "confidence": 0.74 if top_slot_day else 0.66,
        "method": "historical-demand",
        "measurement": "Track sell-through and stock-outs for suggested items versus prior same day/window baselines.",
        "note": "Based on recorded order history by day and meal window; verify final prep quantities with manager judgment.",
    }
    if active_festival:
        recommendation["confidence"] = min(0.86, float(recommendation["confidence"]) + 0.06)
        recommendation["note"] = (
            f"Festival context ({active_festival}) may change demand mix. Validate quantities with live order pace."
        )
    return [recommendation]
