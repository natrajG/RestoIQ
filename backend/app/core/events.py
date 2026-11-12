from uuid import uuid4

from sqlalchemy.orm import Session

from app.models import OperationalEvent


def add_business_event(
    db: Session,
    tenant_id: int,
    restaurant_id: int,
    event_type: str,
    source: str,
    *,
    order_id: int | None = None,
    table_id: int | None = None,
    payload: dict | None = None,
    idempotency_key: str | None = None,
    evidence_source: str | None = None,
    evidence_status: str = "confirmed",
) -> OperationalEvent:
    return OperationalEvent(
        tenant_id=tenant_id,
        restaurant_id=restaurant_id,
        order_id=order_id,
        table_id=table_id,
        event_type=event_type,
        source=source,
        idempotency_key=idempotency_key or str(uuid4()),
        evidence_source=evidence_source or source,
        evidence_status=evidence_status,
        payload=payload or {},
    )
