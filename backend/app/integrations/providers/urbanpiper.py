"""UrbanPiper (Swiggy / Zomato / others through one aggregator).

Built from UrbanPiper's public downstream docs (https://api-docs.urbanpiper.com/downstream/). NOT yet exercised
against a live UrbanPiper account; it is covered by tests that replay the documented sample payloads.

Inbound  : Order Relay webhook (X-UPR-Event-Type 18) creates a delivery order; the order-status webhook
           (60008) applies Cancelled / customer_cancelled.
Outbound : PUT /external/api/v1/orders/{id}/status/ (Acknowledged, Food Ready, Dispatched, Cancelled).
Auth     : UrbanPiper has no HMAC. The webhook is protected by the secret URL token plus a static header
           (X-Api-Token) that the owner configures on the webhook in UrbanPiper Atlas.
"""
import logging
from decimal import Decimal, InvalidOperation
from typing import Mapping

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai_operations.service import create_staff_task
from app.auth.dependencies import Principal
from app.core.events import add_business_event
from app.integrations.base_provider import (
    ConfigField, EventContext, IntegrationProvider, ParsedEvent, ProviderError, ProviderInfo,
)
from app.integrations.capabilities import Capability, Category
from app.integrations.registry import IntegrationRegistry
from app.integrations.security import constant_time_equal
from app.models import (
    IntegrationConnection, IntegrationExternalId, MenuItem, OrderItem, Payment, Restaurant, RestaurantOrder,
)
from app.pos.service import apply_charges, customer_for_phone, money, next_bill_number

logger = logging.getLogger(__name__)

EVT_ORDER_PLACED = "18"
EVT_STATUS_UPDATE = "60008"
TOKEN_HEADERS = ("X-Api-Token", "X_Api_Token", "x_api_token")
DEFAULT_BASE = "https://pos-int.urbanpiper.com"  # UrbanPiper's staging host; production host comes from onboarding
CANCEL_REASONS = {
    "item_out_of_stock", "store_closed", "store_busy", "rider_not_available", "out_of_delivery_radius",
    "connectivity_issue", "total_mismatch", "invalid_item", "option_out_of_stock", "invalid_option",
    "special_instructions", "unspecified",
}


def _header(headers: Mapping[str, str], *names: str) -> str:
    lowered = {k.lower(): v for k, v in headers.items()}
    for n in names:
        if n.lower() in lowered:
            return lowered[n.lower()]
    return ""


def _dec(value) -> Decimal | None:
    try:
        return money(Decimal(str(value)))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _base(credentials: dict[str, str]) -> str:
    base = (credentials.get("api_base_url") or DEFAULT_BASE).strip().rstrip("/")
    if not base.startswith("https://"):
        raise ProviderError("UrbanPiper API URL must use https", retryable=False)
    return base


class UrbanPiperProvider(IntegrationProvider):
    info = ProviderInfo(
        slug="urbanpiper", name="UrbanPiper (Swiggy, Zomato & more)", category=Category.FOOD_DELIVERY, status="live",
        description="Receive Swiggy/Zomato orders through your UrbanPiper account straight into the POS and KOT, "
                    "and send accept / food-ready / cancel back.",
        capabilities=(Capability.RECEIVE_ORDERS, Capability.ORDER_STATUS_SYNC),
        planned_capabilities=("Menu and availability sync", "Rider status"),
        credentials=(
            ConfigField("webhook_token", "Webhook token", secret=True,
                        help="Any secret you choose (16+ characters). Add it as header X-Api-Token on the UrbanPiper webhook."),
            ConfigField("biz_id", "UrbanPiper Biz ID", help="Provided by UrbanPiper at onboarding."),
            ConfigField("api_username", "API username", help="From UrbanPiper (used as 'apikey <username>:<key>')."),
            ConfigField("api_key", "API key", secret=True),
            ConfigField("api_base_url", "API base URL", required=False,
                        help="Production host given by UrbanPiper. Leave blank only for their staging host."),
        ),
        requirements="An UrbanPiper account with Swiggy/Zomato linked. Menu item SKUs must equal the item "
                     "reference IDs in UrbanPiper. Create the Order Relay webhook in Atlas pointing to the URL "
                     "shown after connecting.",
        docs_url="https://api-docs.urbanpiper.com/downstream/",
        rate_limit_per_minute=100,
        notes="Connect this for one outlet. Orders are created for that outlet.",
    )

    # ---- inbound ------------------------------------------------------------------------
    def verify_webhook(self, raw: bytes, headers: Mapping[str, str], credentials: dict[str, str]) -> bool:
        token = credentials.get("webhook_token", "")
        if len(token) < 16 or not constant_time_equal(token, _header(headers, *TOKEN_HEADERS)):
            return False
        biz = _header(headers, "X-UPR-Biz-Id")
        return not biz or not credentials.get("biz_id") or constant_time_equal(str(credentials["biz_id"]).strip(), biz.strip())

    def parse_webhook(self, payload: dict, headers: Mapping[str, str]) -> list[ParsedEvent]:
        evt = _header(headers, "X-UPR-Event-Type").strip()
        if not isinstance(payload, dict):
            raise ProviderError("Invalid payload", retryable=False)
        if evt == EVT_ORDER_PLACED or (not evt and "order" in payload):
            details = (payload.get("order") or {}).get("details") or {}
            if details.get("id") is None:
                raise ProviderError("Order id missing", retryable=False)
            return [ParsedEvent(f"order:{details['id']}", "order.placed", payload)]
        if evt == EVT_STATUS_UPDATE or (not evt and "new_state" in payload):
            oid, state = payload.get("order_id"), str(payload.get("new_state") or "")
            if oid is None or not state:
                raise ProviderError("Status update incomplete", retryable=False)
            return [ParsedEvent(f"status:{oid}:{state}:{payload.get('timestamp_unix', '')}", "order.status", payload)]
        return []  # other UrbanPiper event types are acknowledged and ignored

    def handle_event(self, ctx: EventContext, event: ParsedEvent) -> dict:
        if event.event_type == "order.placed":
            return self._place_order(ctx, event.data)
        if event.event_type == "order.status":
            return self._status_update(ctx, event.data)
        return {"ignored": True}

    def _system(self, ctx: EventContext) -> Principal:
        return Principal(0, ctx.tenant_id, "system", "urbanpiper")

    def _place_order(self, ctx: EventContext, data: dict) -> dict:
        db: Session = ctx.db
        if ctx.restaurant_id is None:
            raise ProviderError("Connect UrbanPiper to a specific outlet to receive orders", retryable=False)
        outlet = db.get(Restaurant, ctx.restaurant_id)
        order_data = data.get("order") or {}
        details = order_data.get("details") or {}
        up_id = str(details["id"])
        mapped = db.scalar(select(IntegrationExternalId).where(
            IntegrationExternalId.connection_id == ctx.connection_id, IntegrationExternalId.entity_type == "order",
            IntegrationExternalId.external_id == up_id))
        if mapped:
            return {"order_id": mapped.local_id, "duplicate": True}

        menu = db.scalars(select(MenuItem).where(MenuItem.restaurant_id == outlet.id, MenuItem.tenant_id == ctx.tenant_id,
                                                 MenuItem.active.is_(True))).all()
        by_sku = {m.sku.strip().lower(): m for m in menu}
        by_name = {m.name.strip().lower(): m for m in menu}
        lines, unmatched = [], []
        for it in order_data.get("items") or []:
            ref = str(it.get("merchant_id") or "").strip().lower()
            title = str(it.get("title") or "").strip()
            m = by_sku.get(ref) or by_name.get(title.lower())
            if not m:
                unmatched.append(title or ref or "?")
                continue
            try:
                qty = int(it.get("quantity") or 1)
            except (TypeError, ValueError):
                qty = 1
            opts = ", ".join(str(o.get("title")) for o in it.get("options_to_add") or [] if o.get("title"))
            note = " | ".join(x for x in (opts and f"+ {opts}", it.get("instructions")) if x)
            lines.append((m, max(qty, 1), _dec(it.get("price")), note or None))
        if unmatched:
            create_staff_task(db, self._system(ctx), outlet.id, "map_delivery_items", "manager",
                              f"UrbanPiper order {up_id}: set menu SKU for {', '.join(unmatched)[:180]}")
            raise ProviderError(f"Unknown items: {', '.join(unmatched)[:200]}. Set each item's SKU to its UrbanPiper "
                                "reference ID, then Retry this job.", retryable=False)

        channel = str(details.get("channel") or "urbanpiper").lower()[:24]
        cust = data.get("customer") or {}
        addr = cust.get("address") or {}
        address = ", ".join(str(addr[k]) for k in ("line_1", "line_2", "landmark", "city", "pin") if addr.get(k)) or None
        composition = (outlet.tax_config or {}).get("gst_scheme") == "composition"
        order = RestaurantOrder(
            tenant_id=ctx.tenant_id, restaurant_id=outlet.id, order_type="delivery", status="submitted", source=channel,
            order_number=next_bill_number(db, ctx.tenant_id, outlet.id, outlet.timezone),
            idempotency_key=f"urbanpiper:{ctx.connection_id}:{up_id}",
            contact_name=(cust.get("name") or "").strip() or None, contact_phone=cust.get("phone"),
            delivery_address=address,
            remark=(f"{channel.title()} #{up_id}" + (f" - {details['instructions']}" if details.get("instructions") else ""))[:300],
            staff_name=channel.title(), service_charge_waived=True,
        )
        known = customer_for_phone(db, ctx.tenant_id, outlet.id, order.contact_phone, order.contact_name)
        order.customer_id = known.id if known else None
        for m, qty, price, note in lines:
            unit = price if price is not None else m.price
            rate = Decimal("0") if composition else m.tax_rate
            base = money(unit * qty)
            order.items.append(OrderItem(tenant_id=ctx.tenant_id, menu_item_id=m.id, item_name=m.name, quantity=qty,
                                         unit_price=unit, tax_rate=rate, line_total=base + money(base * rate / Decimal("100")),
                                         status="active", notes=note))
        apply_charges(order, outlet)
        db.add(order)
        db.flush()
        # Non-cash payments were collected by the aggregator; cash is collected by the rider on delivery.
        remaining = order.total
        for n, p in enumerate(order_data.get("payment") or []):
            amount = _dec(p.get("amount"))
            if str(p.get("option")).lower() == "cash" or not amount or amount <= 0 or remaining <= 0:
                continue
            amount = min(amount, remaining)
            remaining -= amount
            db.add(Payment(tenant_id=ctx.tenant_id, order_id=order.id, method=channel, status="recorded", amount=amount,
                           reference=up_id, idempotency_key=f"urbanpiper:{up_id}:{n}"))
        db.add(IntegrationExternalId(tenant_id=ctx.tenant_id, connection_id=ctx.connection_id, entity_type="order",
                                     local_id=order.id, external_id=up_id))
        db.add(add_business_event(db, ctx.tenant_id, outlet.id, "ORDER_PLACED", "urbanpiper", order_id=order.id,
                                  payload={"order_number": order.order_number, "external_id": up_id},
                                  idempotency_key=f"order:{order.id}:placed"))
        create_staff_task(db, self._system(ctx), outlet.id, "prepare_order", "kitchen",
                          f"Prepare {channel.title()} order {order.order_number}", order_id=order.id)
        from app.integrations.service import enqueue_job
        conn = db.get(IntegrationConnection, ctx.connection_id)
        enqueue_job(db, conn, "order.status", {"upipr_order_id": up_id, "new_status": "Acknowledged"},
                    f"up-ack:{up_id}")
        return {"order_id": order.id, "order_number": order.order_number}

    def _status_update(self, ctx: EventContext, data: dict) -> dict:
        db: Session = ctx.db
        state = str(data.get("new_state") or "")
        if state not in ("Cancelled", "customer_cancelled"):
            return {"ignored": state}  # progress is driven from the POS; only cancellations are applied here
        mapped = db.scalar(select(IntegrationExternalId).where(
            IntegrationExternalId.connection_id == ctx.connection_id, IntegrationExternalId.entity_type == "order",
            IntegrationExternalId.external_id == str(data.get("order_id"))))
        order = db.get(RestaurantOrder, mapped.local_id) if mapped else None
        if not order:
            return {"ignored": "unknown order"}
        if order.status in {"cancelled", "refunded"}:
            return {"order_id": order.id, "already": order.status}
        if order.status in {"paid", "completed"}:
            create_staff_task(db, self._system(ctx), order.restaurant_id, "delivery_cancel_review", "manager",
                              f"{state} received for order {order.order_number} that is already {order.status}",
                              order_id=order.id)
            return {"order_id": order.id, "needs_review": True}
        order.status = "cancelled"
        order.remark = f"Cancelled by aggregator: {data.get('message') or state}"[:300]
        for p in db.scalars(select(Payment).where(Payment.order_id == order.id, Payment.tenant_id == ctx.tenant_id,
                                                  Payment.status == "recorded")):
            p.status = "voided"
        create_staff_task(db, self._system(ctx), order.restaurant_id, "delivery_cancelled", "kitchen",
                          f"Order {order.order_number} was cancelled - stop preparing", order_id=order.id)
        return {"order_id": order.id, "cancelled": True}

    # ---- outbound -----------------------------------------------------------------------
    def validate_connection(self, credentials: dict[str, str]) -> None:
        if len(credentials.get("webhook_token", "")) < 16:
            raise ProviderError("Webhook token must be at least 16 characters", retryable=False)
        _base(credentials)
        # UrbanPiper exposes no documented read-only credential check, so keys are verified on the first order update.

    def execute(self, operation: str, payload: dict, credentials: dict[str, str]) -> dict:
        if operation != "order.status":
            raise ProviderError(f"Operation {operation} is not supported", retryable=False)
        status = payload["new_status"]
        body: dict = {"new_status": status}
        if status == "Cancelled":
            reason = payload.get("reason_code")
            body["message"] = (payload.get("message") or "Cancelled by restaurant")[:200]
            if reason in CANCEL_REASONS:
                body["reason_code"] = reason
            # Swiggy-delivered cancellation is only allowed when UrbanPiper marks the order rejectable.
            if payload.get("swiggy_direct_cancellation"):
                body["extra"] = {"swiggy_direct_cancellation": True}
        url = f"{_base(credentials)}/external/api/v1/orders/{payload['upipr_order_id']}/status/"
        headers = {"Authorization": f"apikey {credentials.get('api_username', '')}:{credentials.get('api_key', '')}",
                   "X-UPR-Biz-Id": str(credentials.get("biz_id", "")), "Content-Type": "application/json"}
        try:
            r = httpx.put(url, json=body, headers=headers, timeout=10)
        except httpx.HTTPError as exc:
            raise ProviderError("Could not reach UrbanPiper", retryable=True) from exc
        if r.status_code in (401, 403):
            raise ProviderError("UrbanPiper rejected the API credentials", retryable=False)
        if r.status_code == 429 or r.status_code >= 500:
            raise ProviderError(f"UrbanPiper returned HTTP {r.status_code}", retryable=True)
        if r.status_code >= 400:
            try:
                err = r.json().get("err_code")
            except Exception:  # noqa: BLE001
                err = None
            if err == "err_order_already_in_status":
                return {"status": status, "already": True}
            # Acknowledge may not have landed yet; backoff will resend.
            retry = err == "err_order_missing_ack"
            raise ProviderError(f"UrbanPiper refused the update: {err or r.status_code}", retryable=retry)
        return {"status": status}


def publish_order_status(db: Session, order: RestaurantOrder, new_status: str, reason_code: str | None = None,
                         message: str | None = None) -> None:
    """Queue a status update for an order that came from UrbanPiper. Never raises: the POS must not fail
    because an aggregator is slow or down."""
    try:
        if not (order.source or "") or order.order_type != "delivery":
            return
        with db.begin_nested():
            row = db.execute(select(IntegrationExternalId, IntegrationConnection).join(
                IntegrationConnection, IntegrationConnection.id == IntegrationExternalId.connection_id).where(
                IntegrationExternalId.tenant_id == order.tenant_id, IntegrationExternalId.entity_type == "order",
                IntegrationExternalId.local_id == order.id, IntegrationConnection.provider == "urbanpiper",
                IntegrationConnection.status == "connected")).first()
            if not row:
                return
            ext, conn = row
            if not (conn.config or {}).get("sync_outbound", True):
                return
            from app.integrations.service import enqueue_job
            from time import time_ns
            payload = {"upipr_order_id": ext.external_id, "new_status": new_status}
            if reason_code:
                payload["reason_code"] = reason_code
            if message:
                payload["message"] = message
            enqueue_job(db, conn, "order.status", payload, f"up-{new_status}:{ext.external_id}:{time_ns()}")
    except Exception:  # noqa: BLE001
        logger.exception("UrbanPiper status publish failed")


IntegrationRegistry.register(UrbanPiperProvider())
