"""Connection management, durable webhook intake, outbox publishing and job execution."""
import logging
import secrets
import time
from datetime import datetime, timedelta, timezone

import redis
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import Principal
from app.core.audit import audit
from app.core.config import settings
from app.db import set_tenant_context
from app.integrations.base_provider import EventContext, IntegrationProvider, ParsedEvent, ProviderError
from app.integrations.capabilities import Capability
from app.integrations.registry import IntegrationRegistry
from app.integrations.security import decrypt_credentials, encrypt_credentials, token_hash
from app.models import (
    DeliveryChannel, IntegrationConnection, IntegrationEvent, IntegrationSyncJob, Restaurant,
)

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 6
CIRCUIT_THRESHOLD = 5
CIRCUIT_OPEN_SECONDS = 300
STALE_RUNNING_SECONDS = 600
MAX_WEBHOOK_BYTES = 256 * 1024

# RestoIQ domain event -> (capability the provider must declare, outbound operation)
OUTBOUND = {
    "menu.item.updated": (Capability.MENU_SYNC, "menu.item.updated"),
    "item.availability.changed": (Capability.ITEM_AVAILABILITY, "item.availability.changed"),
}


def now() -> datetime:
    return datetime.now(timezone.utc)


def backoff_seconds(attempts: int) -> int:
    return min(30 * 2 ** (attempts - 1), 3600)


def visible_providers() -> list[IntegrationProvider]:
    from app.core.config import is_development
    return [p for p in IntegrationRegistry.all() if p.info.status != "mock" or is_development()]


def provider_or_404(slug: str) -> IntegrationProvider:
    provider = IntegrationRegistry.get(slug)
    if not provider:
        raise HTTPException(404, "Unknown provider")
    return provider


def sanitize(message: str) -> str:
    return message[:300]


def connection_or_404(db: Session, tenant_id: int, connection_id: int) -> IntegrationConnection:
    conn = db.scalar(select(IntegrationConnection).where(
        IntegrationConnection.id == connection_id, IntegrationConnection.tenant_id == tenant_id))
    if not conn:
        raise HTTPException(404, "Connection not found")
    return conn


def managed_status(db: Session, tenant_id: int, slug: str) -> str | None:
    """Connection state for providers managed on another page (delivery channels)."""
    n = db.scalar(select(func.count()).select_from(DeliveryChannel).where(
        DeliveryChannel.tenant_id == tenant_id, DeliveryChannel.provider == slug, DeliveryChannel.active.is_(True)))
    return "connected" if n else None


# ---- Connections -------------------------------------------------------------------------

def create_connection(db: Session, principal: Principal, slug: str, restaurant_id: int | None,
                      credentials: dict[str, str], config: dict) -> tuple[IntegrationConnection, str]:
    provider = provider_or_404(slug)
    info = provider.info
    if info.status == "coming_soon":
        raise HTTPException(409, f"{info.name} is not available yet")
    if info.manage_path:
        raise HTTPException(409, f"{info.name} is connected on {info.manage_path}")
    allowed = {f.key for f in info.credentials}
    if set(credentials) - allowed:
        raise HTTPException(422, "Unexpected credential fields")
    missing = [f.label for f in info.credentials if f.required and not credentials.get(f.key, "").strip()]
    if missing:
        raise HTTPException(422, f"Missing: {', '.join(missing)}")
    if restaurant_id is not None and not db.scalar(select(Restaurant.id).where(
            Restaurant.id == restaurant_id, Restaurant.tenant_id == principal.tenant_id)):
        raise HTTPException(404, "Outlet not found")
    try:
        provider.validate_connection(credentials)
    except ProviderError as exc:
        raise HTTPException(422, sanitize(str(exc))) from exc
    token = secrets.token_urlsafe(32)
    existing = db.scalar(select(IntegrationConnection).where(
        IntegrationConnection.tenant_id == principal.tenant_id, IntegrationConnection.provider == slug,
        IntegrationConnection.restaurant_id.is_(None) if restaurant_id is None else IntegrationConnection.restaurant_id == restaurant_id))
    if existing and existing.status != "disabled":
        raise HTTPException(409, "This provider is already connected for that scope")
    if existing:  # reconnect a previously disconnected scope
        conn = existing
        conn.status, conn.credentials_ciphertext, conn.config = "connected", encrypt_credentials(credentials), config or {}
        conn.webhook_token_hash, conn.failure_count, conn.circuit_open_until = token_hash(token), 0, None
        conn.last_error, conn.last_connected_at = None, now()
    else:
        conn = IntegrationConnection(
            tenant_id=principal.tenant_id, restaurant_id=restaurant_id, provider=slug, status="connected",
            credentials_ciphertext=encrypt_credentials(credentials), config=config or {},
            webhook_token_hash=token_hash(token), last_connected_at=now())
        db.add(conn)
    db.flush()
    audit(db, principal, "integration_connected", "integration", conn.id, {"provider": slug})
    return conn, token


def rotate_secrets(db: Session, principal: Principal, conn: IntegrationConnection,
                   credentials: dict[str, str] | None) -> str:
    """Rotates the webhook token and, if given, replaces the stored credentials. Returns the new token."""
    provider = provider_or_404(conn.provider)
    if credentials:
        if set(credentials) - {f.key for f in provider.info.credentials}:
            raise HTTPException(422, "Unexpected credential fields")
        merged = {**decrypt_credentials(conn.credentials_ciphertext), **credentials}
        try:
            provider.validate_connection(merged)
        except ProviderError as exc:
            raise HTTPException(422, sanitize(str(exc))) from exc
        conn.credentials_ciphertext = encrypt_credentials(merged)
    token = secrets.token_urlsafe(32)
    conn.webhook_token_hash = token_hash(token)
    conn.status, conn.failure_count, conn.circuit_open_until, conn.last_error = "connected", 0, None, None
    audit(db, principal, "integration_secret_rotated", "integration", conn.id)
    return token


def disconnect(db: Session, principal: Principal, conn: IntegrationConnection) -> None:
    conn.status = "disabled"
    conn.credentials_ciphertext = ""
    conn.webhook_token_hash = token_hash(secrets.token_urlsafe(32))  # invalidates the old URL
    for job in db.scalars(select(IntegrationSyncJob).where(
            IntegrationSyncJob.connection_id == conn.id, IntegrationSyncJob.status == "pending")):
        job.status, job.error_message, job.completed_at = "dead", "Connection disconnected", now()
    audit(db, principal, "integration_disconnected", "integration", conn.id)


def check_connection(db: Session, principal: Principal, conn: IntegrationConnection) -> dict:
    provider = provider_or_404(conn.provider)
    try:
        provider.health_check(decrypt_credentials(conn.credentials_ciphertext))
    except ProviderError as exc:
        conn.status, conn.last_error = "error", sanitize(str(exc))
        audit(db, principal, "integration_test_failed", "integration", conn.id)
        return {"ok": False, "error": conn.last_error}
    conn.status, conn.last_error, conn.last_connected_at = "connected", None, now()
    audit(db, principal, "integration_tested", "integration", conn.id)
    return {"ok": True}


# ---- Outbox / jobs -----------------------------------------------------------------------

def enqueue_job(db: Session, conn: IntegrationConnection, operation: str, payload: dict,
                idempotency_key: str) -> IntegrationSyncJob | None:
    """Returns None when an identical job already exists (idempotent)."""
    job = IntegrationSyncJob(tenant_id=conn.tenant_id, connection_id=conn.id, operation=operation,
                             payload=payload, idempotency_key=idempotency_key[:120])
    try:
        with db.begin_nested():
            db.add(job)
            db.flush()
    except IntegrityError:
        return None
    return job


def publish_event(db: Session, tenant_id: int, restaurant_id: int | None, event_type: str, data: dict,
                  origin_connection_id: int | None = None) -> int:
    """Fan a RestoIQ event out to connections whose provider declares the capability. Never raises: a provider
    problem must not break the POS request that triggered the event. Events that originated from a connection
    are not echoed back to it (loop prevention)."""
    rule = OUTBOUND.get(event_type)
    if not rule:
        return 0
    capability, operation = rule
    queued = 0
    try:
        with db.begin_nested():
            conns = db.scalars(select(IntegrationConnection).where(
                IntegrationConnection.tenant_id == tenant_id, IntegrationConnection.status == "connected")).all()
            for conn in conns:
                provider = IntegrationRegistry.get(conn.provider)
                if not provider or not provider.supports(capability):
                    continue
                if conn.restaurant_id not in (None, restaurant_id) or conn.id == origin_connection_id:
                    continue
                if not (conn.config or {}).get("sync_outbound", True):
                    continue
                key = f"{event_type}:{data.get('item_id', '')}:{time.time_ns()}"
                if enqueue_job(db, conn, operation, {"event": event_type, **data}, key):
                    queued += 1
    except Exception:  # noqa: BLE001
        logger.exception("Integration publish failed", extra={"event_type": event_type})
        return 0
    return queued


def run_job(db: Session, job: IntegrationSyncJob) -> None:
    conn = db.get(IntegrationConnection, job.connection_id)
    t = now()
    if not conn or conn.status == "disabled":
        job.status, job.error_message, job.completed_at = "dead", "Connection disabled", t
        return
    if conn.circuit_open_until and conn.circuit_open_until > t:
        job.next_attempt_at = conn.circuit_open_until  # circuit open: wait without burning an attempt
        return
    provider = IntegrationRegistry.get(conn.provider)
    if not provider:
        job.status, job.error_message, job.completed_at = "dead", "Provider no longer available", t
        return
    job.status, job.started_at = "running", t
    job.attempts += 1
    event = None
    try:
        creds = decrypt_credentials(conn.credentials_ciphertext)
        if job.operation == "event.process":
            event = db.get(IntegrationEvent, job.payload["event_id"])
            parsed = ParsedEvent(event.external_event_id, event.event_type, event.payload)
            result = provider.handle_event(EventContext(db, conn.tenant_id, conn.restaurant_id, conn.id), parsed)
        else:
            result = provider.execute(job.operation, job.payload, creds)
    except Exception as exc:  # noqa: BLE001
        retryable = exc.retryable if isinstance(exc, ProviderError) else True
        message = sanitize(str(exc) if isinstance(exc, ProviderError) else f"Internal error: {type(exc).__name__}")
        if not isinstance(exc, ProviderError):
            logger.exception("Integration job crashed", extra={"job_id": job.id})
        job.error_message = message
        conn.failure_count += 1
        conn.last_error = message
        if conn.failure_count >= CIRCUIT_THRESHOLD:
            conn.circuit_open_until = now() + timedelta(seconds=CIRCUIT_OPEN_SECONDS)
        if retryable and job.attempts < MAX_ATTEMPTS:
            job.status = "pending"
            job.next_attempt_at = now() + timedelta(seconds=backoff_seconds(job.attempts))
        else:
            job.status, job.completed_at = "dead", now()
        if event:
            event.retry_count = job.attempts
            event.error = message
            event.processing_status = "failed" if job.status == "dead" else "received"
        return
    job.status, job.result, job.error_message, job.completed_at = "succeeded", result or {}, None, now()
    conn.failure_count, conn.circuit_open_until, conn.last_error, conn.last_sync_at = 0, None, None, now()
    if event:
        event.processing_status, event.processed_at, event.error = "processed", now(), None


def retry_job(db: Session, principal: Principal, job: IntegrationSyncJob) -> None:
    if job.status not in ("dead", "pending"):
        raise HTTPException(409, f"Job is {job.status}")
    job.status, job.attempts, job.next_attempt_at, job.completed_at, job.error_message = "pending", 0, now(), None, None
    conn = db.get(IntegrationConnection, job.connection_id)
    if conn:
        conn.circuit_open_until = None
    audit(db, principal, "integration_job_retried", "integration_job", job.id)


def process_due_jobs(session_factory, limit: int = 50) -> int:
    """Worker entry point. Safe to run concurrently (SKIP LOCKED) and after a crash (stale jobs are recovered)."""
    done = 0
    with session_factory() as db:
        tenant_ids = list(db.scalars(select(IntegrationConnection.tenant_id).where(
            IntegrationConnection.status != "disabled").distinct()))
        db.rollback()
    for tenant_id in tenant_ids:
        with session_factory() as db:
            set_tenant_context(db, tenant_id)
            stale = now() - timedelta(seconds=STALE_RUNNING_SECONDS)
            for job in db.scalars(select(IntegrationSyncJob).where(
                    IntegrationSyncJob.status == "running", IntegrationSyncJob.started_at < stale)):
                job.status = "pending"
            db.commit()
            set_tenant_context(db, tenant_id)  # the context is transaction-local; commit() cleared it
            jobs = db.scalars(select(IntegrationSyncJob).where(
                IntegrationSyncJob.status == "pending", IntegrationSyncJob.next_attempt_at <= now())
                .order_by(IntegrationSyncJob.next_attempt_at).limit(limit).with_for_update(skip_locked=True)).all()
            for job in jobs:
                set_tenant_context(db, tenant_id)
                run_job(db, job)
                db.commit()
                done += 1
    return done


# ---- Webhooks ----------------------------------------------------------------------------

def _throttle(conn: IntegrationConnection, limit: int) -> None:
    try:
        client = redis.Redis.from_url(settings.redis_url, socket_timeout=1)
        key = f"integration-webhook:{conn.id}:{int(time.time() // 60)}"
        count = client.incr(key)
        if count == 1:
            client.expire(key, 120)
        if count > limit:
            raise HTTPException(429, "Too many requests")
    except redis.RedisError:
        logger.warning("Webhook throttle unavailable")


def ingest_webhook(db: Session, slug: str, token: str, raw: bytes, headers) -> dict:
    """Resolve the connection from the secret token (never from the payload), verify, store durably, queue."""
    if len(raw) > MAX_WEBHOOK_BYTES:
        raise HTTPException(413, "Payload too large")
    provider = IntegrationRegistry.get(slug)
    conn = db.scalar(select(IntegrationConnection).where(IntegrationConnection.webhook_token_hash == token_hash(token)))
    if not provider or not conn or conn.provider != slug or conn.status != "connected" or provider.info.manage_path:
        raise HTTPException(404, "Unknown webhook")
    _throttle(conn, provider.info.rate_limit_per_minute)
    if not provider.verify_webhook(raw, headers, decrypt_credentials(conn.credentials_ciphertext)):
        raise HTTPException(401, "Invalid signature")
    try:
        import json
        events = provider.parse_webhook(json.loads(raw), headers)
    except (ProviderError, ValueError) as exc:
        raise HTTPException(422, "Invalid payload") from exc
    set_tenant_context(db, conn.tenant_id)
    accepted = duplicates = 0
    for ev in events:
        row = IntegrationEvent(tenant_id=conn.tenant_id, connection_id=conn.id, provider=slug,
                               event_type=ev.event_type[:80], external_event_id=ev.external_id[:120], payload=ev.data)
        try:
            with db.begin_nested():
                db.add(row)
                db.flush()
        except IntegrityError:
            duplicates += 1
            continue
        enqueue_job(db, conn, "event.process", {"event_id": row.id}, f"event:{row.id}")
        accepted += 1
    return {"accepted": accepted, "duplicates": duplicates}
