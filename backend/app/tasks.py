import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select

from app.celery_app import celery
from app.core.config import settings
from app.db import SessionLocal
from app.db import set_tenant_context
from app.models import Camera, GeneratedReport, Restaurant, Tenant

logger = logging.getLogger(__name__)


@celery.task(name="app.tasks.cleanup_expired_recordings")
def cleanup_expired_recordings() -> int:
    """Delete only managed recording files older than the configured retention period."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.video_retention_days)
    removed = 0
    root = Path(settings.upload_dir).resolve()
    with SessionLocal() as db:
        rows = db.scalars(select(Camera).where(Camera.recording_path.is_not(None))).all()
        for camera in rows:
            path = Path(camera.recording_path or "").resolve()
            if not path.is_relative_to(root) or not path.is_file():
                continue
            if datetime.fromtimestamp(path.stat().st_mtime, timezone.utc) < cutoff:
                path.unlink()
                camera.recording_path = None
                removed += 1
        db.commit()
    logger.info("Recording retention cleanup complete", extra={"removed_files": removed})
    return removed


@celery.task(name="app.tasks.generate_reports")
def generate_reports(period: str) -> int:
    """Build and store the weekly/monthly report for every outlet of every restaurant."""
    from app.core.subscriptions import subscription_state
    from app.reports.builder import build_report

    created = 0
    with SessionLocal() as db:
        for tenant_id in list(db.scalars(select(Tenant.id))):
            try:
                set_tenant_context(db, tenant_id)
                if subscription_state(db, tenant_id)["locked"]:
                    continue
                for outlet in list(db.scalars(select(Restaurant).where(Restaurant.tenant_id == tenant_id))):
                    payload = build_report(db, tenant_id, outlet, period)
                    today = datetime.now(timezone.utc).date()
                    exists = db.scalar(select(GeneratedReport.id).where(
                        GeneratedReport.restaurant_id == outlet.id, GeneratedReport.period == period,
                        GeneratedReport.period_end == today))
                    if not exists:
                        db.add(GeneratedReport(tenant_id=tenant_id, restaurant_id=outlet.id, period=period,
                                               period_end=today, payload=payload))
                        created += 1
                db.commit()
            except Exception:
                db.rollback()
                logger.exception("Report generation failed for tenant %s", tenant_id)
    return created


@celery.task(name="app.tasks.send_renewal_reminders")
def send_renewal_reminders() -> int:
    """Email the owner 7, 3 and 1 day(s) before a trial or paid plan ends (the job runs once a day)."""
    from app.core import email_templates, mailer
    from app.core.subscriptions import _latest_subscription
    from app.models import ReminderLog, User

    sent = 0
    today = datetime.now(timezone.utc).date()
    with SessionLocal() as db:
        for tenant_id in list(db.scalars(select(Tenant.id))):
            try:
                set_tenant_context(db, tenant_id)
                sub = _latest_subscription(db, tenant_id)
                if not sub or sub.ends_at is None or sub.status not in ("trial", "active"):
                    continue
                days = (sub.ends_at.date() - today).days
                if days not in (7, 3, 1):
                    continue
                from app.models import AutoRenewal
                if db.scalar(select(AutoRenewal.id).where(AutoRenewal.tenant_id == tenant_id, AutoRenewal.status.in_(("authenticated", "active")))):
                    continue  # the plan renews itself
                owner = db.scalar(select(User).where(User.tenant_id == tenant_id, User.role == "owner", User.is_active.is_(True)).order_by(User.id))
                if owner:
                    status = mailer.send_safe(owner.email, *email_templates.reminder(owner.full_name or "there", days, sub.status == "trial"))
                    db.add(ReminderLog(tenant_id=tenant_id, kind="auto", days_left=days, to_email=owner.email, status=status))
                    db.commit()
                    sent += 1
            except Exception:
                logger.exception("Renewal reminder failed for tenant %s", tenant_id)
    return sent


@celery.task(name="app.tasks.process_integration_jobs")
def process_integration_jobs() -> int:
    """Run due integration outbox jobs and queued webhook events (retries use exponential backoff)."""
    from app.integrations import providers  # noqa: F401
    from app.integrations.service import process_due_jobs
    return process_due_jobs(SessionLocal)
