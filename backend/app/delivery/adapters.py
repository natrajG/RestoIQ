"""Provider adapters for the delivery integration engine.

An adapter does two things for one provider: verify the inbound request and translate its payload into the
canonical order (`WebhookIn`). Everything after that (item matching, order creation, kitchen tasks, summary)
is shared. To add a provider, subclass ProviderAdapter and register it in PROVIDERS. Only add a provider-specific
parser once the provider's real payload and signing scheme are confirmed from its documentation.
"""
import hashlib
import hmac
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class WebhookItem(BaseModel):
    sku: str | None = Field(default=None, max_length=64)
    name: str = Field(min_length=1, max_length=160)
    quantity: int = Field(ge=1, le=99)
    unit_price: Decimal | None = Field(default=None, ge=0)


class WebhookCustomer(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=20)


class WebhookIn(BaseModel):
    event: Literal["order.created", "order.cancelled"] = "order.created"
    external_order_id: str = Field(min_length=1, max_length=80)
    customer: WebhookCustomer = WebhookCustomer()
    delivery_address: str | None = Field(default=None, max_length=400)
    items: list[WebhookItem] = Field(default_factory=list, max_length=100)
    total: Decimal | None = Field(default=None, ge=0)
    commission: Decimal = Field(default=Decimal("0"), ge=0)
    payment: Literal["prepaid", "cod"] = "prepaid"
    notes: str | None = Field(default=None, max_length=300)


class ProviderAdapter:
    key = "other"
    label = "Other / generic"
    inbound_orders = True
    outbound_sync = False  # accept/reject, status, menu and stock push are not implemented for any provider
    notes = "Canonical JSON signed with HMAC-SHA256 in X-Signature."

    def verify(self, raw: bytes, headers, secret: str) -> bool:
        expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, headers.get("X-Signature", "").removeprefix("sha256=").lower())

    def parse(self, payload: dict) -> "WebhookIn":
        return WebhookIn.model_validate(payload)


class CanonicalAdapter(ProviderAdapter):
    pass


def _canonical(key: str, label: str, notes: str) -> ProviderAdapter:
    a = CanonicalAdapter()
    a.key, a.label, a.notes = key, label, notes
    return a


# Swiggy and Zomato currently use the canonical format because they are reached through middleware or a
# partner-specific adapter that we cannot write without their confirmed documentation and credentials.
PROVIDERS: dict[str, ProviderAdapter] = {a.key: a for a in (
    _canonical("swiggy", "Swiggy", "Via middleware that posts canonical JSON. Direct API needs partner onboarding."),
    _canonical("zomato", "Zomato", "Via middleware that posts canonical JSON. Direct API needs partner onboarding and credentials."),
    _canonical("urbanpiper", "UrbanPiper", "Middleware; map its payload to canonical JSON (adapter pending a real account)."),
    ProviderAdapter(),
)}


def get_adapter(provider: str) -> ProviderAdapter:
    return PROVIDERS.get(provider, PROVIDERS["other"])
