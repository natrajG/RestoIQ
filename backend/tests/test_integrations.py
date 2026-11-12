"""Integration engine tests. They need the application database (run inside the api container) and roll back
everything they write."""
import json
from datetime import timedelta

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.auth.dependencies import Principal
from app.db import engine, get_db, set_tenant_context
from app.integrations import providers  # noqa: F401
from app.integrations import service as svc
from app.integrations.base_provider import IntegrationProvider, ProviderError
from app.integrations.providers.mock import MockProvider
from app.integrations.registry import IntegrationRegistry
from app.integrations.router import mask_payload
from app.integrations.security import decrypt_credentials, hmac_sha256_hex
from app.main import app
from app.models import IntegrationConnection, IntegrationEvent, IntegrationSyncJob, Restaurant, Tenant

SECRET = "s3cret-signing-value"


@pytest.fixture()
def env():
    conn = engine.connect()
    outer = conn.begin()
    factory = sessionmaker(bind=conn, join_transaction_mode="create_savepoint", autoflush=False, expire_on_commit=False)
    db = factory()
    tenants = []
    for name in ("itest-A", "itest-B"):
        t = Tenant(name=name + str(id(conn)))
        db.add(t)
        db.flush()
        set_tenant_context(db, t.id)
        o = Restaurant(tenant_id=t.id, name="Outlet")
        db.add(o)
        db.flush()
        tenants.append((t.id, o.id))
    MockProvider.calls = []
    MockProvider.fail_next = 0

    def override():
        yield db

    app.dependency_overrides[get_db] = override
    yield db, tenants, factory
    app.dependency_overrides.pop(get_db, None)
    db.close()
    outer.rollback()
    conn.close()


def principal(tid):
    return Principal(0, tid, "owner", "o@example.com")


def connect(db, tenants, who=0, restaurant=True):
    tid, oid = tenants[who]
    set_tenant_context(db, tid)
    return svc.create_connection(db, principal(tid), "mock", oid if restaurant else None, {"signing_secret": SECRET}, {})


def post(client, slug, token, body, sig=None):
    raw = json.dumps(body).encode()
    return client.post(f"/api/v1/integrations/webhooks/{slug}/{token}", content=raw,
                       headers={"X-Mock-Signature": sig or hmac_sha256_hex(SECRET, raw)})


def jobs(db, conn):
    return db.scalars(select(IntegrationSyncJob).where(IntegrationSyncJob.connection_id == conn.id).order_by(IntegrationSyncJob.id)).all()


def run_all(db, factory, rounds=1):
    return svc.process_due_jobs(factory)


# ---- registry / capabilities --------------------------------------------------------------

def test_registry_rejects_duplicates_and_declares_capabilities():
    with pytest.raises(ValueError):
        IntegrationRegistry.register(MockProvider())
    assert IntegrationRegistry.get("razorpay").info.capabilities
    for slug in ("tally", "whatsapp", "shopify", "zoho_books"):
        p = IntegrationRegistry.get(slug)
        assert p.info.status == "coming_soon" and not p.info.capabilities


def test_mock_hidden_outside_development(monkeypatch):
    monkeypatch.setattr("app.core.config.is_development", lambda: False)
    assert "mock" not in [p.info.slug for p in svc.visible_providers()]


def test_coming_soon_and_managed_providers_cannot_be_connected(env):
    db, tenants, _ = env
    set_tenant_context(db, tenants[0][0])
    for slug in ("tally", "swiggy"):
        with pytest.raises(HTTPException) as e:
            svc.create_connection(db, principal(tenants[0][0]), slug, None, {}, {})
        assert e.value.status_code == 409


# ---- credentials / connections ------------------------------------------------------------

def test_credentials_are_encrypted_and_never_in_api_dict(env):
    db, tenants, _ = env
    conn, _ = connect(db, tenants)
    assert SECRET not in conn.credentials_ciphertext
    assert decrypt_credentials(conn.credentials_ciphertext)["signing_secret"] == SECRET
    from app.integrations.router import _conn_dict
    assert SECRET not in json.dumps(_conn_dict(conn), default=str)


def test_missing_or_unexpected_credentials_rejected(env):
    db, tenants, _ = env
    set_tenant_context(db, tenants[0][0])
    with pytest.raises(HTTPException):
        svc.create_connection(db, principal(tenants[0][0]), "mock", None, {}, {})
    with pytest.raises(HTTPException):
        svc.create_connection(db, principal(tenants[0][0]), "mock", None, {"signing_secret": "x", "evil": "y"}, {})


def test_cannot_attach_connection_to_another_tenants_outlet(env):
    db, tenants, _ = env
    set_tenant_context(db, tenants[0][0])
    with pytest.raises(HTTPException) as e:
        svc.create_connection(db, principal(tenants[0][0]), "mock", tenants[1][1], {"signing_secret": SECRET}, {})
    assert e.value.status_code == 404


def test_tenant_isolation(env):
    db, tenants, _ = env
    conn, token = connect(db, tenants, 0)
    client = TestClient(app)
    assert post(client, "mock", token, {"id": "e1", "type": "x"}).status_code == 200
    with pytest.raises(HTTPException):
        svc.connection_or_404(db, tenants[1][0], conn.id)
    set_tenant_context(db, tenants[1][0])  # row-level security hides tenant A's rows
    assert db.scalars(select(IntegrationEvent)).all() == []
    assert db.scalars(select(IntegrationSyncJob)).all() == []


# ---- webhook engine ------------------------------------------------------------------------

def test_webhook_validation_and_duplicates(env):
    db, tenants, _ = env
    conn, token = connect(db, tenants)
    client = TestClient(app)
    body = {"id": "evt-1", "type": "order.created", "data": {"a": 1}}
    assert post(client, "mock", token, body, sig="bad").status_code == 401
    assert post(client, "mock", "wrong-token", body).status_code == 404
    assert post(client, "razorpay", token, body).status_code == 404  # token belongs to another provider
    assert post(client, "mock", token, {"type": "no-id"}).status_code == 422
    assert post(client, "mock", token, body).json() == {"accepted": 1, "duplicates": 0}
    assert post(client, "mock", token, body).json() == {"accepted": 0, "duplicates": 1}
    set_tenant_context(db, tenants[0][0])
    assert len(db.scalars(select(IntegrationEvent)).all()) == 1
    assert len(jobs(db, conn)) == 1


def test_payload_tenant_id_is_ignored(env):
    db, tenants, _ = env
    conn, token = connect(db, tenants, 0)
    client = TestClient(app)
    post(client, "mock", token, {"id": "e2", "type": "x", "tenant_id": tenants[1][0], "data": {"tenant_id": tenants[1][0]}})
    set_tenant_context(db, tenants[0][0])
    assert db.scalar(select(IntegrationEvent)).tenant_id == tenants[0][0]


def test_oversized_webhook_rejected(env):
    db, tenants, _ = env
    _, token = connect(db, tenants)
    r = TestClient(app).post(f"/api/v1/integrations/webhooks/mock/{token}", content=b"x" * (svc.MAX_WEBHOOK_BYTES + 1))
    assert r.status_code == 413


def test_rate_limit(env, monkeypatch):
    db, tenants, _ = env
    _, token = connect(db, tenants)

    class Fake:
        def incr(self, key): return 10_000
        def expire(self, *a): pass

    monkeypatch.setattr("redis.Redis.from_url", lambda *a, **k: Fake())
    assert post(TestClient(app), "mock", token, {"id": "r1", "type": "x"}).status_code == 429


def test_event_processed_by_worker(env):
    db, tenants, factory = env
    conn, token = connect(db, tenants)
    post(TestClient(app), "mock", token, {"id": "e3", "type": "order.created"})
    assert run_all(db, factory) == 1
    set_tenant_context(db, tenants[0][0])
    ev = db.scalar(select(IntegrationEvent))
    assert ev.processing_status == "processed" and ev.processed_at
    db.refresh(conn)
    assert conn.last_sync_at


# ---- retries, dead letter, circuit breaker -------------------------------------------------

def test_failed_event_retries_with_backoff_then_dead_letters_and_can_be_retried(env):
    db, tenants, factory = env
    conn, token = connect(db, tenants)
    post(TestClient(app), "mock", token, {"id": "bad", "type": "x", "data": {"fail": True}})
    set_tenant_context(db, tenants[0][0])
    job = jobs(db, conn)[0]
    for attempt in range(1, svc.MAX_ATTEMPTS + 1):
        db.refresh(conn)
        conn.circuit_open_until = None
        job.next_attempt_at = svc.now() - timedelta(seconds=1)
        db.flush()
        svc.process_due_jobs(factory)
        set_tenant_context(db, tenants[0][0])
        db.refresh(job)
        assert job.attempts == attempt
        if attempt < svc.MAX_ATTEMPTS:
            assert job.status == "pending" and job.next_attempt_at > svc.now()
    assert job.status == "dead"
    assert db.scalar(select(IntegrationEvent)).processing_status == "failed"
    svc.retry_job(db, principal(tenants[0][0]), job)
    assert (job.status, job.attempts) == ("pending", 0)


def test_backoff_is_exponential_and_capped():
    assert [svc.backoff_seconds(n) for n in (1, 2, 3)] == [30, 60, 120]
    assert svc.backoff_seconds(30) == 3600


def test_provider_outage_then_recovery_and_circuit_breaker(env):
    db, tenants, factory = env
    conn, _ = connect(db, tenants)
    tid, oid = tenants[0]
    set_tenant_context(db, tid)
    MockProvider.fail_next = 100
    svc.publish_event(db, tid, oid, "menu.item.updated", {"item_id": 1, "price": "10"})
    job = jobs(db, conn)[0]
    for _ in range(svc.CIRCUIT_THRESHOLD):
        job.next_attempt_at = svc.now() - timedelta(seconds=1)
        db.flush()
        svc.process_due_jobs(factory)
        set_tenant_context(db, tid)
        db.refresh(job)
    db.refresh(conn)
    assert conn.circuit_open_until and conn.circuit_open_until > svc.now()
    attempts = job.attempts
    job.next_attempt_at = svc.now() - timedelta(seconds=1)
    db.flush()
    svc.process_due_jobs(factory)  # open circuit: job is deferred, no attempt consumed, provider not called
    set_tenant_context(db, tid)
    db.refresh(job)
    assert job.attempts == attempts and MockProvider.calls == []
    MockProvider.fail_next = 0
    db.refresh(conn)
    conn.circuit_open_until = None
    job.next_attempt_at = svc.now() - timedelta(seconds=1)
    db.flush()
    svc.process_due_jobs(factory)
    set_tenant_context(db, tid)
    db.refresh(job); db.refresh(conn)
    assert job.status == "succeeded" and conn.failure_count == 0 and MockProvider.calls


def test_non_retryable_error_goes_straight_to_dead_letter(env, monkeypatch):
    db, tenants, factory = env
    conn, _ = connect(db, tenants)
    tid, oid = tenants[0]
    set_tenant_context(db, tid)
    svc.publish_event(db, tid, oid, "menu.item.updated", {"item_id": 1})

    def boom(self, op, payload, creds):
        raise ProviderError("rejected", retryable=False)

    monkeypatch.setattr(MockProvider, "execute", boom)
    svc.process_due_jobs(factory)
    set_tenant_context(db, tid)
    assert jobs(db, conn)[0].status == "dead"


def test_stale_running_job_is_recovered(env):
    db, tenants, factory = env
    conn, _ = connect(db, tenants)
    tid, oid = tenants[0]
    set_tenant_context(db, tid)
    svc.publish_event(db, tid, oid, "menu.item.updated", {"item_id": 1})
    job = jobs(db, conn)[0]
    job.status, job.started_at = "running", svc.now() - timedelta(seconds=svc.STALE_RUNNING_SECONDS + 5)
    db.flush()
    svc.process_due_jobs(factory)
    set_tenant_context(db, tid)
    db.refresh(job)
    assert job.status == "succeeded"


# ---- outbound publishing --------------------------------------------------------------------

def test_publish_respects_capability_scope_origin_and_setting(env):
    db, tenants, _ = env
    tid, oid = tenants[0]
    mock_conn, _ = connect(db, tenants)
    other_outlet = Restaurant(tenant_id=tid, name="Other")
    db.add(other_outlet); db.flush()
    assert svc.publish_event(db, tid, other_outlet.id, "menu.item.updated", {"item_id": 7}) == 0  # outlet-scoped
    assert svc.publish_event(db, tid, oid, "unknown.event", {}) == 0
    assert svc.publish_event(db, tid, oid, "menu.item.updated", {"item_id": 7}, origin_connection_id=mock_conn.id) == 0  # no echo
    mock_conn.config = {"sync_outbound": False}
    assert svc.publish_event(db, tid, oid, "menu.item.updated", {"item_id": 7}) == 0
    mock_conn.config = {}
    assert svc.publish_event(db, tid, oid, "menu.item.updated", {"item_id": 7}) == 1
    # another tenant's publish never reaches this connection
    set_tenant_context(db, tenants[1][0])
    assert svc.publish_event(db, tenants[1][0], tenants[1][1], "menu.item.updated", {"item_id": 7}) == 0


def test_publish_skips_providers_without_capability(env):
    db, tenants, _ = env
    tid, oid = tenants[0]
    set_tenant_context(db, tid)
    conn = IntegrationConnection(tenant_id=tid, restaurant_id=oid, provider="razorpay", status="connected", webhook_token_hash="h" * 64)
    db.add(conn); db.flush()
    assert svc.publish_event(db, tid, oid, "menu.item.updated", {"item_id": 1}) == 0


def test_publish_never_raises(env, monkeypatch):
    db, tenants, _ = env
    connect(db, tenants)
    monkeypatch.setattr(svc, "enqueue_job", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("db down")))
    assert svc.publish_event(db, tenants[0][0], tenants[0][1], "menu.item.updated", {"item_id": 1}) == 0


def test_disconnect_invalidates_url_and_cancels_pending(env):
    db, tenants, _ = env
    conn, token = connect(db, tenants)
    tid, oid = tenants[0]
    svc.publish_event(db, tid, oid, "menu.item.updated", {"item_id": 1})
    svc.disconnect(db, principal(tid), conn)
    assert post(TestClient(app), "mock", token, {"id": "x", "type": "y"}).status_code == 404
    assert [j.status for j in jobs(db, conn)] == ["dead"]
    assert conn.credentials_ciphertext == ""


def test_rotate_changes_webhook_token(env):
    db, tenants, _ = env
    conn, old = connect(db, tenants)
    new = svc.rotate_secrets(db, principal(tenants[0][0]), conn, None)
    db.flush()
    client = TestClient(app)
    assert post(client, "mock", old, {"id": "a", "type": "b"}).status_code == 404
    assert post(client, "mock", new, {"id": "a", "type": "b"}).status_code == 200


# ---- providers -------------------------------------------------------------------------------

def test_razorpay_signature_and_parsing():
    p = IntegrationRegistry.get("razorpay")
    raw = b'{"event":"payment.captured"}'
    creds = {"webhook_secret": "whsec"}
    sig = hmac_sha256_hex("whsec", raw)
    assert p.verify_webhook(raw, {"X-Razorpay-Signature": sig}, creds)
    assert not p.verify_webhook(raw, {"X-Razorpay-Signature": "0" * 64}, creds)
    assert not p.verify_webhook(raw, {"X-Razorpay-Signature": sig}, {"webhook_secret": ""})
    ev = p.parse_webhook(json.loads(raw), {"X-Razorpay-Event-Id": "evt_1"})[0]
    assert (ev.external_id, ev.event_type) == ("evt_1", "payment.captured")


def test_razorpay_connection_validation_maps_errors(monkeypatch):
    p = IntegrationRegistry.get("razorpay")
    monkeypatch.setattr(httpx, "get", lambda *a, **k: httpx.Response(401))
    with pytest.raises(ProviderError) as e:
        p.validate_connection({"key_id": "a", "key_secret": "b"})
    assert e.value.retryable is False
    monkeypatch.setattr(httpx, "get", lambda *a, **k: httpx.Response(503))
    with pytest.raises(ProviderError) as e:
        p.validate_connection({"key_id": "a", "key_secret": "b"})
    assert e.value.retryable is True

    def down(*a, **k):
        raise httpx.ConnectError("x")

    monkeypatch.setattr(httpx, "get", down)
    with pytest.raises(ProviderError):
        p.validate_connection({})


def test_sensitive_payload_fields_masked():
    out = mask_payload({"customer": {"phone": "99999", "name": "A"}, "api_key": "z", "items": [{"token": "t", "n": 1}]})
    assert out["customer"]["phone"] == "••••" and out["api_key"] == "••••" and out["items"][0]["token"] == "••••"
    assert out["customer"]["name"] == "A" and out["items"][0]["n"] == 1


def test_duplicate_active_connection_rejected_and_reconnect_after_disconnect(env):
    db, tenants, _ = env
    conn, token = connect(db, tenants, restaurant=False)
    with pytest.raises(HTTPException) as e:
        connect(db, tenants, restaurant=False)  # tenant-wide scope (NULL outlet) must also be unique
    assert e.value.status_code == 409
    svc.disconnect(db, principal(tenants[0][0]), conn)
    again, new_token = connect(db, tenants, restaurant=False)
    assert again.id == conn.id and again.status == "connected" and new_token != token
