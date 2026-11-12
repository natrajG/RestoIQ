from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Customer, DiningTable, MenuCategory, MenuItem, Restaurant, RestaurantOrder


def outlet_by_id(db: Session, tenant_id: int, outlet_id: int) -> Restaurant | None:
    return db.scalar(select(Restaurant).where(Restaurant.id == outlet_id, Restaurant.tenant_id == tenant_id))


def order_by_id(db: Session, tenant_id: int, order_id: int, for_update: bool = False) -> RestaurantOrder | None:
    statement = select(RestaurantOrder).where(
        RestaurantOrder.id == order_id, RestaurantOrder.tenant_id == tenant_id,
    )
    if for_update:
        statement = statement.with_for_update()
    return db.scalar(statement)


def table_by_id(db: Session, tenant_id: int, outlet_id: int, table_id: int) -> DiningTable | None:
    return db.scalar(select(DiningTable).where(
        DiningTable.id == table_id, DiningTable.restaurant_id == outlet_id,
        DiningTable.tenant_id == tenant_id,
    ))


def customer_by_id(db: Session, tenant_id: int, outlet_id: int, customer_id: int) -> Customer | None:
    return db.scalar(select(Customer).where(
        Customer.id == customer_id, Customer.restaurant_id == outlet_id,
        Customer.tenant_id == tenant_id,
    ))


def menu_items_by_ids(db: Session, tenant_id: int, outlet_id: int, item_ids: set[int]) -> list[MenuItem]:
    return db.scalars(select(MenuItem).where(
        MenuItem.id.in_(item_ids), MenuItem.restaurant_id == outlet_id,
        MenuItem.tenant_id == tenant_id, MenuItem.active.is_(True),
    )).all()


def menu_categories(db: Session, tenant_id: int, outlet_id: int) -> list[MenuCategory]:
    return db.scalars(select(MenuCategory).where(
        MenuCategory.restaurant_id == outlet_id, MenuCategory.tenant_id == tenant_id,
    ).order_by(MenuCategory.sort_order, MenuCategory.name)).all()
