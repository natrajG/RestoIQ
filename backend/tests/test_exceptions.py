"""Exceptions report test (run inside the api container; everything rolls back)."""
from decimal import Decimal

from sqlalchemy.orm import sessionmaker

from app.auth.dependencies import Principal
from app.core.audit import audit
from app.db import engine, set_tenant_context
from app.models import Restaurant, RestaurantOrder, Tenant, User
from app.pos.exceptions import exceptions


def test_report_lists_void_by_staff():
    conn = engine.connect()
    outer = conn.begin()
    db = sessionmaker(bind=conn, join_transaction_mode="create_savepoint", autoflush=False, expire_on_commit=False)()
    try:
        t = Tenant(name="exc-" + str(id(conn)))
        db.add(t)
        db.flush()
        set_tenant_context(db, t.id)
        o = Restaurant(tenant_id=t.id, name="O")
        db.add(o)
        db.flush()
        u = User(tenant_id=t.id, email="c@x.com", full_name="Asha", password_hash="x", role="cashier")
        db.add(u)
        order = RestaurantOrder(tenant_id=t.id, restaurant_id=o.id, order_number="E/1", status="cancelled", total=Decimal("250"))
        db.add(order)
        db.flush()
        p = Principal(u.id, t.id, "cashier", "c@x.com")
        audit(db, p, "order_voided", "order", str(order.id), {"reason": "walked out"})
        audit(db, p, "order_charges_changed", "order", str(order.id), {"discount_type": "percent", "discount_value": "0", "tip": "10"})
        db.flush()
        r = exceptions(o.id, None, None, db, Principal(0, t.id, "owner", "o@x.com"))
        assert len(r["rows"]) == 1  # the tip-only change is not an exception
        assert r["rows"][0]["staff"] == "Asha" and Decimal(r["rows"][0]["amount"]) == 250
        assert r["by_staff"][0]["actions"]["order_voided"]["count"] == 1
    finally:
        db.close()
        outer.rollback()
        conn.close()
