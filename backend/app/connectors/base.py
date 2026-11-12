from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class CanonicalPosEvent:
    source: str
    event_id: str
    event_type: str
    payload: dict[str, Any]


class PosConnector(Protocol):
    """Translate a vendor payload into an idempotent event; no connector may mirror-write POS data."""

    def normalize(self, payload: dict[str, Any]) -> CanonicalPosEvent: ...


class CanonicalWebhookConnector:
    """Vendor-neutral boundary; vendor-specific authentication and payload mapping belong in adapters."""

    source = "external_pos"

    def normalize(self, payload: dict[str, Any]) -> CanonicalPosEvent:
        event_id = str(payload.get("external_event_id", "")).strip()
        event_type = str(payload.get("event_type", "")).strip()
        body = payload.get("payload")
        if not event_id or not event_type or not isinstance(body, dict):
            raise ValueError("Canonical POS events require external_event_id, event_type, and object payload")
        return CanonicalPosEvent(self.source, event_id, event_type, body)
