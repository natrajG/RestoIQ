from typing import Protocol

from sqlalchemy.orm import Session

from app.models import AuditLog


class Actor(Protocol):
    tenant_id: int
    user_id: int


def audit(
    db: Session,
    actor: Actor,
    action: str,
    resource: str,
    resource_id: int | str | None = None,
    details: dict | None = None,
) -> None:
    db.add(AuditLog(
        tenant_id=actor.tenant_id,
        user_id=actor.user_id or None,
        action=action,
        resource_type=resource,
        resource_id=str(resource_id) if resource_id is not None else None,
        details=details or {},
    ))
