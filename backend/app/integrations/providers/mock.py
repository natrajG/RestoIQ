"""Test double. Not a real integration: it never contacts anything. Hidden from the marketplace outside development."""
from typing import Mapping

from app.integrations.base_provider import ConfigField, IntegrationProvider, ParsedEvent, ProviderError, ProviderInfo
from app.integrations.capabilities import Capability, Category
from app.integrations.registry import IntegrationRegistry
from app.integrations.security import constant_time_equal, hmac_sha256_hex


class MockProvider(IntegrationProvider):
    info = ProviderInfo(
        slug="mock", name="Test sandbox", category=Category.OTHER, status="mock",
        description="Built-in test double used to exercise the engine. Does not connect to any real service.",
        capabilities=(Capability.RECEIVE_ORDERS, Capability.MENU_SYNC, Capability.ITEM_AVAILABILITY),
        credentials=(ConfigField("signing_secret", "Signing secret", secret=True),),
    )
    calls: list[tuple[str, dict]] = []
    fail_next = 0  # number of upcoming execute() calls that raise a retryable error

    def verify_webhook(self, raw: bytes, headers: Mapping[str, str], credentials: dict[str, str]) -> bool:
        return constant_time_equal(hmac_sha256_hex(credentials.get("signing_secret", ""), raw), headers.get("X-Mock-Signature", ""))

    def parse_webhook(self, payload: dict, headers: Mapping[str, str]) -> list[ParsedEvent]:
        if not payload.get("id") or not payload.get("type"):
            raise ProviderError("Invalid payload", retryable=False)
        return [ParsedEvent(str(payload["id"]), str(payload["type"]), payload.get("data") or {})]

    def handle_event(self, ctx, event: ParsedEvent) -> dict:
        if event.data.get("fail"):
            raise ProviderError("Simulated handler failure", retryable=True)
        return {"handled": event.event_type}

    def validate_connection(self, credentials: dict[str, str]) -> None:
        if not credentials.get("signing_secret"):
            raise ProviderError("Signing secret required", retryable=False)

    def execute(self, operation: str, payload: dict, credentials: dict[str, str]) -> dict:
        if MockProvider.fail_next > 0:
            MockProvider.fail_next -= 1
            raise ProviderError("Simulated provider outage", retryable=True)
        MockProvider.calls.append((operation, payload))
        return {"ok": True}


IntegrationRegistry.register(MockProvider())
