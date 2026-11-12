"""Split-bill tests (run inside the api container; everything rolls back)."""
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import sessionmaker

from app.auth.dependencies import Principal
from app.db import engine, set_tenant_context
from app.models import DiningTable, MenuItem, OrderItem, Restaurant, RestaurantOrder, Tenant, User
from app.pos.table_actions import SplitInput, SplitLine, split_order, table_live


@pytest.fixture()
def ctx():
    conn = engine.connect()
    outer = conn.begin()
    db = sessionmaker(bind=conn, join_transaction_mode="create_savepoint", autoflush=False, expire_on_commit=False)()
    t = Tenant(name="split-" + str(id(conn)))
    db.add(t)
    db.flush()
    set_tenant_context(db, t.id)
    o = Restaurant(tenant_id=t.id, name="O")
    db.add(o)
    db.flush()
    table = DiningTable(tenant_id=t.id, restaurant_id=o.id, name="T1", status="OCCUPIED")
    mi = MenuItem(tenant_id=t.id, restaurant_id=o.id, name="Dosa", sku="D1", price=Decimal("100"), tax_rate=Decimal("5"))
    db.add_all([table, mi])
    db.flush()
    order = RestaurantOrder(tenant_id=t.id, restaurant_id=o.id, table_id=table.id, order_number="S/1", status="served")
    db.add(order)
    db.flush()
    for name, q in (("Dosa", 3), ("Tea", 2)):
        db.add(OrderItem(tenant_id=t.id, order_id=order.id, menu_item_id=mi.id, item_name=name, quantity=q,
                         unit_price=Decimal("100"), tax_rate=Decimal("5"), line_total=Decimal("100") * q))
    db.flush()
    db.refresh(order)
    p = Principal(0, t.id, "owner", "o@x.com")
    yield db, p, order, table
    db.close()
    outer.rollback()
    conn.close()


def test_split_partial_quantity_conserves_totals(ctx):
    db, p, order, table = ctx
    before = Decimal("500")
    ids = {i.item_name: i.id for i in order.items}
    r = split_order(order.id, SplitInput(lines=[SplitLine(item_id=ids["Dosa"], quantity=1), SplitLine(item_id=ids["Tea"], quantity=2)]), db, p)
    a, b = r["original"], r["new"]
    assert [i["quantity"] for i in a["items"]] == [2] and sorted(i["quantity"] for i in b["items"]) == [1, 2]
    assert Decimal(a["subtotal"]) + Decimal(b["subtotal"]) == before
    assert a["table_id"] == b["table_id"] == table.id and a["order_number"] != b["order_number"]
    assert Decimal(a["total"]) == Decimal("210.00") and Decimal(b["total"]) == Decimal("315.00")
    live = table_live(order.restaurant_id, db, p)
    assert live[table.id]["bills"] == 2 and Decimal(live[table.id]["amount"]) == Decimal("525.00")


def test_split_validation(ctx):
    db, p, order, _ = ctx
    ids = [i.id for i in order.items]
    with pytest.raises(HTTPException) as e:
        split_order(order.id, SplitInput(lines=[SplitLine(item_id=ids[0], quantity=4)]), db, p)
    assert e.value.status_code == 422
    with pytest.raises(HTTPException) as e:
        split_order(order.id, SplitInput(lines=[SplitLine(item_id=ids[0], quantity=3), SplitLine(item_id=ids[1], quantity=2)]), db, p)
    assert e.value.status_code == 422
    with pytest.raises(HTTPException) as e:
        split_order(order.id, SplitInput(lines=[SplitLine(item_id=99999, quantity=1)]), db, p)
    assert e.value.status_code == 404
