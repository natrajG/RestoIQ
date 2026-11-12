"""UrbanPiper adapter tests, using payloads shaped like UrbanPiper's documented samples (no live account)."""
import json
from decimal import Decimal

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import set_tenant_context
from app.integrations import service as svc
from app.integrations.providers.urbanpiper import UrbanPiperProvider, publish_order_status
from app.main import app
from app.models import IntegrationSyncJob, MenuItem, Payment, RestaurantOrder
from tests.test_integrations import env, jobs, principal  # noqa: F401

TOKEN = "a-long-static-header-token"
CREDS = {"webhook_token": TOKEN, "biz_id": "123", "api_username": "biz_adm_x", "api_key": "k3y",
         "api_base_url": "https://pos-int.urbanpiper.com"}


def connect_up(db, tenants):
    tid, oid = tenants[0]
    set_tenant_context(db, tid)
    return svc.create_connection(db, principal(tid), "urbanpiper", oid, CREDS, {})


def order_payload(oid=555, sku="D1", payment="wallet_credit"):
    return {"customer": {"name": "Asha", "phone": "9999999999", "address": {"line_1": "12 MG Rd", "city": "Pune"}},
            "order": {"details": {"id": oid, "channel": "zomato", "order_total": 105, "instructions": "less spicy"},
                      "items": [{"title": "Dosa", "quantity": 1, "price": 100, "merchant_id": sku,
                                 "options_to_add": [{"title": "Extra cheese"}]}],
                      "payment": [{"amount": 105, "option": payment}]}}


def post(client, token, body, evt="18", auth=TOKEN):
    h = {"X-UPR-Event-Type": evt, "X-UPR-Biz-Id": "123"}
    if auth:
        h["X-Api-Token"] = auth
    return client.post(f"/api/v1/integrations/webhooks/urbanpiper/{token}", content=json.dumps(body).encode(), headers=h)


def add_item(db, tenants, sku="D1"):
    tid, oid = tenants[0]
    db.add(MenuItem(tenant_id=tid, restaurant_id=oid, name="Dosa", sku=sku, price=Decimal("100"), tax_rate=Decimal("5")))
    db.flush()


def test_rejects_missing_or_wrong_header(env):
    db, tenants, _ = env
    conn, token = connect_up(db, tenants)
    c = TestClient(app)
    assert post(c, token, order_payload(), auth=None).status_code == 401
    assert post(c, token, order_payload(), auth="wrong-wrong-wrong-wrong").status_code == 401


def test_order_created_acknowledged_and_idempotent(env, monkeypatch):
    db, tenants, factory = env
    conn, token = connect_up(db, tenants)
    add_item(db, tenants)
    c = TestClient(app)
    assert post(c, token, order_payload()).status_code == 200
    assert post(c, token, order_payload()).status_code == 200  # replay
    calls = []

    def fake_put(url, json=None, headers=None, timeout=None):
        calls.append((url, json, headers))
        return httpx.Response(200, json={"status": "success"})

    monkeypatch.setattr(httpx, "put", fake_put)
    svc.process_due_jobs(factory)
    svc.process_due_jobs(factory)
    set_tenant_context(db, tenants[0][0])
    orders = db.scalars(select(RestaurantOrder)).all()
    assert len(orders) == 1 and orders[0].order_type == "delivery" and orders[0].source == "zomato"
    assert orders[0].items[0].notes == "+ Extra cheese"
    pays = db.scalars(select(Payment)).all()
    assert len(pays) == 1 and pays[0].amount == orders[0].total
    assert calls[0][0].endswith("/external/api/v1/orders/555/status/") and calls[0][1]["new_status"] == "Acknowledged"
    assert calls[0][2]["Authorization"] == "apikey biz_adm_x:k3y"


def test_cash_order_records_no_payment(env):
    db, tenants, factory = env
    conn, token = connect_up(db, tenants)
    add_item(db, tenants)
    post(TestClient(app), token, order_payload(payment="cash"))
    svc.process_due_jobs(factory)
    set_tenant_context(db, tenants[0][0])
    assert db.scalars(select(Payment)).all() == []


def test_unmatched_items_dead_letter_then_retry_after_sku_fix(env, monkeypatch):
    db, tenants, factory = env
    conn, token = connect_up(db, tenants)
    post(TestClient(app), token, order_payload(sku="NOPE"))
    svc.process_due_jobs(factory)
    set_tenant_context(db, tenants[0][0])
    job = jobs(db, conn)[0]
    assert job.status == "dead" and "Unknown items" in job.error_message
    monkeypatch.setattr(httpx, "put", lambda *a, **k: httpx.Response(200, json={}))
    add_item(db, tenants, sku="NOPE")
    svc.retry_job(db, principal(tenants[0][0]), job)
    db.flush()
    svc.process_due_jobs(factory)
    svc.process_due_jobs(factory)
    set_tenant_context(db, tenants[0][0])
    assert len(db.scalars(select(RestaurantOrder)).all()) == 1


def test_aggregator_cancellation_cancels_and_voids_payment(env, monkeypatch):
    db, tenants, factory = env
    conn, token = connect_up(db, tenants)
    add_item(db, tenants)
    monkeypatch.setattr(httpx, "put", lambda *a, **k: httpx.Response(200, json={}))
    c = TestClient(app)
    post(c, token, order_payload())
    svc.process_due_jobs(factory)
    cancel = {"order_id": 555, "new_state": "Cancelled", "prev_state": "Placed", "timestamp_unix": 1, "message": "Customer"}
    assert post(c, token, cancel, evt="60008").status_code == 200
    svc.process_due_jobs(factory)
    set_tenant_context(db, tenants[0][0])
    assert db.scalar(select(RestaurantOrder)).status == "cancelled"
    assert db.scalar(select(Payment)).status == "voided"


def test_pos_status_publishes_only_for_urbanpiper_orders(env, monkeypatch):
    db, tenants, factory = env
    conn, token = connect_up(db, tenants)
    add_item(db, tenants)
    monkeypatch.setattr(httpx, "put", lambda *a, **k: httpx.Response(200, json={}))
    post(TestClient(app), token, order_payload())
    svc.process_due_jobs(factory)
    set_tenant_context(db, tenants[0][0])
    order = db.scalar(select(RestaurantOrder))
    publish_order_status(db, order, "Food Ready")
    assert [j.payload["new_status"] for j in jobs(db, conn) if j.operation == "order.status"] == ["Acknowledged", "Food Ready"]
    order.source = None
    order.order_type = "takeaway"
    publish_order_status(db, order, "Cancelled", "unspecified")
    assert len([j for j in jobs(db, conn) if j.operation == "order.status"]) == 2


def test_outbound_error_handling(monkeypatch):
    p = UrbanPiperProvider()
    body = {"upipr_order_id": "1", "new_status": "Food Ready"}
    from app.integrations.base_provider import ProviderError
    monkeypatch.setattr(httpx, "put", lambda *a, **k: httpx.Response(400, json={"err_code": "err_order_already_in_status"}))
    assert p.execute("order.status", body, CREDS)["already"]
    monkeypatch.setattr(httpx, "put", lambda *a, **k: httpx.Response(400, json={"err_code": "err_order_missing_ack"}))
    with pytest.raises(ProviderError) as e:
        p.execute("order.status", body, CREDS)
    assert e.value.retryable
    monkeypatch.setattr(httpx, "put", lambda *a, **k: httpx.Response(400, json={"message": "Callback requested instead"}))
    with pytest.raises(ProviderError) as e:
        p.execute("order.status", body, CREDS)
    assert not e.value.retryable
    monkeypatch.setattr(httpx, "put", lambda *a, **k: httpx.Response(503))
    with pytest.raises(ProviderError) as e:
        p.execute("order.status", body, CREDS)
    assert e.value.retryable
