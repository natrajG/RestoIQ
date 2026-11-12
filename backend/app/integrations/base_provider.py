"""Trusted provider adapter contract. Adapters are code in this repository and are registered explicitly;
no third-party code or configuration is ever executed."""
from dataclasses import dataclass, field
from typing import Any, Mapping

from app.integrations.capabilities import Capability, Category


class ProviderError(Exception):
    """Raised by adapters. retryable=False sends the job straight to dead-letter."""

    def __init__(self, message: str, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


@dataclass(frozen=True)
class ConfigField:
    key: str
    label: str
    secret: bool = False
    required: bool = True
    help: str = ""


@dataclass
class ParsedEvent:
    external_id: str
    event_type: str
    data: dict[str, Any]


@dataclass
class ProviderInfo:
    slug: str
    name: str
    category: Category
    description: str
    status: str = "coming_soon"
    capabilities: tuple[Capability, ...] = ()
    planned_capabilities: tuple[str, ...] = ()
    credentials: tuple[ConfigField, ...] = ()
    manage_path: str | None = None  # connection is managed on an existing RestoIQ page
    requirements: str = ""
    docs_url: str | None = None
    rate_limit_per_minute: int = 60
    notes: str = ""


class IntegrationProvider:
    info: ProviderInfo

    def verify_webhook(self, raw: bytes, headers: Mapping[str, str], credentials: dict[str, str]) -> bool:
        return False

    def parse_webhook(self, payload: dict, headers: Mapping[str, str]) -> list[ParsedEvent]:
        raise ProviderError("Provider does not accept webhooks", retryable=False)

    def handle_event(self, ctx: "EventContext", event: ParsedEvent) -> dict:
        return {}

    def validate_connection(self, credentials: dict[str, str]) -> None:
        """Raise ProviderError if the credentials are not usable."""

    def execute(self, operation: str, payload: dict, credentials: dict[str, str]) -> dict:
        raise ProviderError(f"Operation {operation} is not supported", retryable=False)

    def health_check(self, credentials: dict[str, str]) -> bool:
        self.validate_connection(credentials)
        return True

    def supports(self, capability: Capability) -> bool:
        return capability in self.info.capabilities


@dataclass
class EventContext:
    db: Any
    tenant_id: int
    restaurant_id: int | None
    connection_id: int
    extra: dict = field(default_factory=dict)
