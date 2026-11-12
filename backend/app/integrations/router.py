from datetime import timedelta
from typing import Any

from starlette.concurrency import run_in_threadpool
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import Principal, require_roles
from app.db import get_db, set_tenant_context
from app.integrations import providers  # noqa: F401  (registers adapters)
from app.integrations import service as svc
from app.integrations.base_provider import IntegrationProvider
from app.integrations.capabilities import Capability
from app.models import IntegrationConnection, IntegrationEvent, IntegrationSyncJob

router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])
ADMINS = ("owner", "admin")
SENSITIVE = ("secret", "token", "password", "authorization", "key", "email", "phone", "contact", "card", "vpa")


def mask_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: ("••••" if any(s in k.lower() for s in SENSITIVE) else mask_payload(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [mask_payload(v) for v in value[:50]]
    return value


def _provider_dict(p: IntegrationProvider, conns: list[IntegrationConnection], managed: str | None) -> dict:
    i = p.info
    status = "connected" if managed or any(c.status == "connected" for c in conns) else (
        "error" if any(c.status == "error" for c in conns) else "not_connected")
    synced = [c.last_sync_at for c in conns if c.last_sync_at]
    return {
        "slug": i.slug, "name": i.name, "category": i.category.value, "description": i.description,
        "availability": i.status, "capabilities": [c.value for c in i.capabilities],
        "planned_capabilities": list(i.planned_capabilities), "requirements": i.requirements, "docs_url": i.docs_url,
        "manage_path": i.manage_path, "connection_status": status,
        "credential_fields": [{"key": f.key, "label": f.label, "secret": f.secret, "required": f.required, "help": f.help}
                              for f in i.credentials],
        "connection_ids": [c.id for c in conns if c.status != "disabled"],
        "last_sync_at": max(synced).isoformat() if synced else None,
    }


def _conn_dict(c: IntegrationConnection) -> dict:
    return {
        "id": c.id, "provider": c.provider, "restaurant_id": c.restaurant_id, "status": c.status,
        "config": c.config, "last_error": c.last_error, "failure_count": c.failure_count,
        "circuit_open": bool(c.circuit_open_until and c.circuit_open_until > svc.now()),
        "last_connected_at": c.last_connected_at, "last_sync_at": c.last_sync_at, "created_at": c.created_at,
    }


def _webhook_url(request: Request, provider: str, token: str) -> str:
    base = str(request.base_url).rstrip("/")
    return f"{base}/api/v1/integrations/webhooks/{provider}/{token}"


@router.get("/providers")
def list_providers(db: Session = Depends(get_db), principal: Principal = Depends(require_roles(*ADMINS))):
    conns = db.scalars(select(IntegrationConnection).where(IntegrationConnection.tenant_id == principal.tenant_id)).all()
    out = []
    for p in svc.visible_providers():
        mine = [c for c in conns if c.provider == p.info.slug]
        managed = svc.managed_status(db, principal.tenant_id, p.info.slug) if p.info.manage_path else None
        out.append(_provider_dict(p, mine, managed))
    return out


@router.get("/providers/{slug}")
def get_provider(slug: str, db: Session = Depends(get_db), principal: Principal = Depends(require_roles(*ADMINS))):
    p = svc.provider_or_404(slug)
    mine = db.scalars(select(IntegrationConnection).where(
        IntegrationConnection.tenant_id == principal.tenant_id, IntegrationConnection.provider == slug)).all()
    managed = svc.managed_status(db, principal.tenant_id, slug) if p.info.manage_path else None
    return _provider_dict(p, list(mine), managed)


class ConnectIn(BaseModel):
    provider: str = Field(max_length=40)
    restaurant_id: int | None = None
    credentials: dict[str, str] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)


@router.get("/connections")
def list_connections(db: Session = Depends(get_db), principal: Principal = Depends(require_roles(*ADMINS))):
    rows = db.scalars(select(IntegrationConnection).where(IntegrationConnection.tenant_id == principal.tenant_id)
                      .order_by(IntegrationConnection.id)).all()
    return [_conn_dict(c) for c in rows]


@router.post("/connections", status_code=201)
def create_connection(body: ConnectIn, request: Request, db: Session = Depends(get_db),
                      principal: Principal = Depends(require_roles(*ADMINS))):
    conn, token = svc.create_connection(db, principal, body.provider, body.restaurant_id, body.credentials, body.config)
    out = _conn_dict(conn)
    out["webhook_url"] = _webhook_url(request, conn.provider, token)  # shown once
    return out


@router.get("/connections/{connection_id}")
def get_connection(connection_id: int, db: Session = Depends(get_db), principal: Principal = Depends(require_roles(*ADMINS))):
    return _conn_dict(svc.connection_or_404(db, principal.tenant_id, connection_id))


class SettingsIn(BaseModel):
    sync_outbound: bool | None = None


@router.patch("/connections/{connection_id}")
def update_settings(connection_id: int, body: SettingsIn, db: Session = Depends(get_db),
                    principal: Principal = Depends(require_roles(*ADMINS))):
    conn = svc.connection_or_404(db, principal.tenant_id, connection_id)
    cfg = dict(conn.config or {})
    if body.sync_outbound is not None:
        cfg["sync_outbound"] = body.sync_outbound
    conn.config = cfg
    return _conn_dict(conn)


class RotateIn(BaseModel):
    credentials: dict[str, str] | None = None


@router.post("/connections/{connection_id}/rotate")
def rotate(connection_id: int, body: RotateIn, request: Request, db: Session = Depends(get_db),
           principal: Principal = Depends(require_roles(*ADMINS))):
    conn = svc.connection_or_404(db, principal.tenant_id, connection_id)
    if conn.status == "disabled":
        raise HTTPException(409, "Connection is disconnected; create a new one")
    token = svc.rotate_secrets(db, principal, conn, body.credentials)
    return {**_conn_dict(conn), "webhook_url": _webhook_url(request, conn.provider, token)}


@router.delete("/connections/{connection_id}", status_code=204)
def disconnect(connection_id: int, db: Session = Depends(get_db), principal: Principal = Depends(require_roles(*ADMINS))):
    svc.disconnect(db, principal, svc.connection_or_404(db, principal.tenant_id, connection_id))


@router.post("/connections/{connection_id}/test")
def test(connection_id: int, db: Session = Depends(get_db), principal: Principal = Depends(require_roles(*ADMINS))):
    return svc.check_connection(db, principal, svc.connection_or_404(db, principal.tenant_id, connection_id))


@router.post("/connections/{connection_id}/sync", status_code=202)
def manual_sync(connection_id: int, db: Session = Depends(get_db), principal: Principal = Depends(require_roles(*ADMINS))):
    conn = svc.connection_or_404(db, principal.tenant_id, connection_id)
    provider = svc.provider_or_404(conn.provider)
    if conn.status != "connected" or not (provider.supports(Capability.MENU_SYNC) or provider.supports(Capability.ITEM_AVAILABILITY)):
        raise HTTPException(409, "This connection has no synchronization capability")
    job = svc.enqueue_job(db, conn, "sync.manual", {}, f"manual:{svc.time.time_ns()}")
    return {"job_id": job.id if job else None}


@router.get("/events")
def list_events(connection_id: int | None = None, status: str | None = None, limit: int = 50,
                db: Session = Depends(get_db), principal: Principal = Depends(require_roles(*ADMINS))):
    q = select(IntegrationEvent).where(IntegrationEvent.tenant_id == principal.tenant_id)
    if connection_id:
        q = q.where(IntegrationEvent.connection_id == connection_id)
    if status:
        q = q.where(IntegrationEvent.processing_status == status)
    rows = db.scalars(q.order_by(IntegrationEvent.id.desc()).limit(min(limit, 200))).all()
    return [{"id": e.id, "provider": e.provider, "connection_id": e.connection_id, "event_type": e.event_type,
             "external_event_id": e.external_event_id, "processing_status": e.processing_status,
             "retry_count": e.retry_count, "error": e.error, "created_at": e.created_at,
             "processed_at": e.processed_at, "payload": mask_payload(e.payload)} for e in rows]


@router.get("/jobs")
def list_jobs(connection_id: int | None = None, status: str | None = None, limit: int = 50,
              db: Session = Depends(get_db), principal: Principal = Depends(require_roles(*ADMINS))):
    q = select(IntegrationSyncJob).where(IntegrationSyncJob.tenant_id == principal.tenant_id)
    if connection_id:
        q = q.where(IntegrationSyncJob.connection_id == connection_id)
    if status:
        q = q.where(IntegrationSyncJob.status == status)
    rows = db.scalars(q.order_by(IntegrationSyncJob.id.desc()).limit(min(limit, 200))).all()
    return [{"id": j.id, "connection_id": j.connection_id, "operation": j.operation, "status": j.status,
             "attempts": j.attempts, "error_message": j.error_message, "next_attempt_at": j.next_attempt_at,
             "created_at": j.created_at, "completed_at": j.completed_at} for j in rows]


@router.post("/jobs/{job_id}/retry")
def retry(job_id: int, db: Session = Depends(get_db), principal: Principal = Depends(require_roles(*ADMINS))):
    job = db.scalar(select(IntegrationSyncJob).where(
        IntegrationSyncJob.id == job_id, IntegrationSyncJob.tenant_id == principal.tenant_id))
    if not job:
        raise HTTPException(404, "Job not found")
    svc.retry_job(db, principal, job)
    return {"id": job.id, "status": job.status}


@router.get("/monitoring")
def monitoring(db: Session = Depends(get_db), principal: Principal = Depends(require_roles(*ADMINS))):
    tid = principal.tenant_id
    since = svc.now() - timedelta(hours=24)
    by_status = dict(db.execute(select(IntegrationSyncJob.status, func.count()).where(
        IntegrationSyncJob.tenant_id == tid).group_by(IntegrationSyncJob.status)).all())
    events_24h = dict(db.execute(select(IntegrationEvent.processing_status, func.count()).where(
        IntegrationEvent.tenant_id == tid, IntegrationEvent.created_at >= since).group_by(IntegrationEvent.processing_status)).all())
    conns = db.scalars(select(IntegrationConnection).where(
        IntegrationConnection.tenant_id == tid, IntegrationConnection.status != "disabled")).all()
    last_ok = max((c.last_sync_at for c in conns if c.last_sync_at), default=None)
    return {
        "connections": len(conns), "active": sum(c.status == "connected" for c in conns),
        "errors": [{"id": c.id, "provider": c.provider, "error": c.last_error, "circuit_open": bool(c.circuit_open_until and c.circuit_open_until > svc.now())}
                   for c in conns if c.last_error],
        "jobs": {"pending": by_status.get("pending", 0), "running": by_status.get("running", 0),
                 "succeeded": by_status.get("succeeded", 0), "dead": by_status.get("dead", 0)},
        "events_24h": events_24h, "last_successful_sync": last_ok,
    }


@router.post("/webhooks/{provider}/{token}")
async def webhook(provider: str, token: str, request: Request, db: Session = Depends(get_db)):
    raw = await request.body()
    return await run_in_threadpool(svc.ingest_webhook, db, provider, token, raw, request.headers)
