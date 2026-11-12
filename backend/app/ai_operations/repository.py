from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Camera, DiningTable, FestivalCalendar, OrderItem, RestaurantOrder, StaffTask


@dataclass(frozen=True)
class MenuDemandPoint:
    item_name: str
    quantity: int
    ordered_at: datetime


def cameras_for_outlet(db: Session, tenant_id: int, outlet_id: int) -> list[Camera]:
    return db.scalars(select(Camera).where(
        Camera.tenant_id == tenant_id, Camera.restaurant_id == outlet_id,
    ).order_by(Camera.name)).all()


def task_by_id(db: Session, tenant_id: int, outlet_id: int, task_id: int) -> StaffTask | None:
    return db.scalar(select(StaffTask).where(
        StaffTask.id == task_id, StaffTask.tenant_id == tenant_id,
        StaffTask.restaurant_id == outlet_id,
    ))


def tasks_for_outlet(db: Session, tenant_id: int, outlet_id: int) -> list[StaffTask]:
    return db.scalars(select(StaffTask).where(
        StaffTask.tenant_id == tenant_id,
        StaffTask.restaurant_id == outlet_id,
        StaffTask.status.not_in(["completed", "cancelled"]),
    ).order_by(StaffTask.created_at)).all()


def table_by_id(db: Session, tenant_id: int, outlet_id: int, table_id: int) -> DiningTable | None:
    return db.scalar(select(DiningTable).where(
        DiningTable.id == table_id,
        DiningTable.tenant_id == tenant_id,
        DiningTable.restaurant_id == outlet_id,
    ))


def camera_by_id(db: Session, tenant_id: int, outlet_id: int, camera_id: int) -> Camera | None:
    return db.scalar(select(Camera).where(
        Camera.id == camera_id,
        Camera.tenant_id == tenant_id,
        Camera.restaurant_id == outlet_id,
    ))


def recent_menu_demand(
    db: Session,
    tenant_id: int,
    outlet_id: int,
    *,
    lookback_days: int = 56,
) -> list[MenuDemandPoint]:
    start = datetime.utcnow() - timedelta(days=lookback_days)
    rows = db.execute(
        select(OrderItem.item_name, OrderItem.quantity, RestaurantOrder.created_at)
        .join(RestaurantOrder, RestaurantOrder.id == OrderItem.order_id)
        .where(
            OrderItem.tenant_id == tenant_id,
            RestaurantOrder.tenant_id == tenant_id,
            RestaurantOrder.restaurant_id == outlet_id,
            RestaurantOrder.created_at >= start,
            RestaurantOrder.status.not_in(["cancelled"]),
        )
    ).all()
    return [
        MenuDemandPoint(item_name=item_name, quantity=quantity, ordered_at=ordered_at)
        for item_name, quantity, ordered_at in rows
    ]


def active_festival_name(
    db: Session,
    tenant_id: int,
    outlet_id: int,
    local_date,
    state_code: str | None,
) -> str | None:
    outlet_festival = db.scalar(
        select(FestivalCalendar.name)
        .where(
            FestivalCalendar.tenant_id == tenant_id,
            FestivalCalendar.restaurant_id == outlet_id,
            FestivalCalendar.active.is_(True),
            FestivalCalendar.starts_on <= local_date,
            FestivalCalendar.ends_on >= local_date,
        )
        .order_by(FestivalCalendar.starts_on.desc())
    )
    if outlet_festival:
        return outlet_festival
    if state_code:
        state_festival = db.scalar(
            select(FestivalCalendar.name)
            .where(
                FestivalCalendar.tenant_id == tenant_id,
                FestivalCalendar.restaurant_id.is_(None),
                FestivalCalendar.state_code == state_code,
                FestivalCalendar.active.is_(True),
                FestivalCalendar.starts_on <= local_date,
                FestivalCalendar.ends_on >= local_date,
            )
            .order_by(FestivalCalendar.starts_on.desc())
        )
        if state_festival:
            return state_festival
    tenant_festival = db.scalar(
        select(FestivalCalendar.name)
        .where(
            FestivalCalendar.tenant_id == tenant_id,
            FestivalCalendar.restaurant_id.is_(None),
            FestivalCalendar.active.is_(True),
            FestivalCalendar.starts_on <= local_date,
            FestivalCalendar.ends_on >= local_date,
        )
        .order_by(FestivalCalendar.starts_on.desc())
    )
    if tenant_festival:
        return tenant_festival
    return None
