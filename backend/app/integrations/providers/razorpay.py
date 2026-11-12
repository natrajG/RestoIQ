"""Razorpay: webhook authenticity check and read-only credential validation.

Based on Razorpay's documented scheme: X-Razorpay-Signature is the hex HMAC-SHA256 of the raw body using the
webhook secret, and X-Razorpay-Event-Id identifies a delivery. Events are stored for audit; this adapter does not
yet change RestoIQ payments. Not exercised against a live Razorpay account.
"""
import hashlib
from typing import Mapping

import httpx

from app.integrations.base_provider import ConfigField, IntegrationProvider, ParsedEvent, ProviderError, ProviderInfo
from app.integrations.capabilities import Capability, Category
from app.integrations.registry import IntegrationRegistry
from app.integrations.security import constant_time_equal, hmac_sha256_hex


class RazorpayProvider(IntegrationProvider):
    info = ProviderInfo(
        slug="razorpay", name="Razorpay", category=Category.PAYMENTS, status="live",
        description="Verify and record Razorpay payment webhooks for this restaurant's own Razorpay account.",
        capabilities=(Capability.PAYMENT_EVENTS,),
        planned_capabilities=("Create payment links/orders", "Refunds", "Automatic payment status update on bills"),
        credentials=(
            ConfigField("key_id", "Key ID"),
            ConfigField("key_secret", "Key secret", secret=True),
            ConfigField("webhook_secret", "Webhook secret", secret=True, help="Set the same secret on the Razorpay webhook."),
        ),
        requirements="A Razorpay account with API keys and a webhook pointing to the URL shown after connecting.",
        docs_url="https://razorpay.com/docs/webhooks/",
        rate_limit_per_minute=120,
    )

    def verify_webhook(self, raw: bytes, headers: Mapping[str, str], credentials: dict[str, str]) -> bool:
        secret = credentials.get("webhook_secret", "")
        return bool(secret) and constant_time_equal(hmac_sha256_hex(secret, raw), headers.get("X-Razorpay-Signature", ""))

    def parse_webhook(self, payload: dict, headers: Mapping[str, str]) -> list[ParsedEvent]:
        event = payload.get("event")
        if not isinstance(event, str):
            raise ProviderError("Invalid payload", retryable=False)
        event_id = headers.get("X-Razorpay-Event-Id") or hashlib.sha256(repr(sorted(payload.items())).encode()).hexdigest()[:40]
        return [ParsedEvent(event_id, event, payload)]

    def validate_connection(self, credentials: dict[str, str]) -> None:
        try:
            r = httpx.get("https://api.razorpay.com/v1/payments", params={"count": 1}, timeout=10,
                          auth=(credentials.get("key_id", ""), credentials.get("key_secret", "")))
        except httpx.HTTPError as exc:
            raise ProviderError("Could not reach Razorpay", retryable=True) from exc
        if r.status_code in (401, 403):
            raise ProviderError("Razorpay rejected the API keys", retryable=False)
        if r.status_code >= 400:
            raise ProviderError(f"Razorpay returned HTTP {r.status_code}", retryable=r.status_code >= 500)


IntegrationRegistry.register(RazorpayProvider())
