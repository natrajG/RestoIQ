from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import InventoryItem


def item_by_id(db: Session, tenant_id: int, outlet_id: int, item_id: int) -> InventoryItem | None:
    return db.scalar(select(InventoryItem).where(
        InventoryItem.id == item_id, InventoryItem.tenant_id == tenant_id,
        InventoryItem.restaurant_id == outlet_id,
    ))


def items_for_outlet(db: Session, tenant_id: int, outlet_id: int) -> list[InventoryItem]:
    return db.scalars(select(InventoryItem).where(
        InventoryItem.tenant_id == tenant_id, InventoryItem.restaurant_id == outlet_id,
    ).order_by(InventoryItem.name)).all()


def add_item(db: Session, item: InventoryItem) -> InventoryItem:
    db.add(item)
    db.flush()
    return item
