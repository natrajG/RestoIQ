> **Superseded:** UrbanPiper is now integrated through the Integration Engine (see docs/INTEGRATION_ENGINE.md). The text below describes the older hidden canonical webhook.

> **On hold:** the Delivery apps page and the Swiggy/Zomato/UrbanPiper cards are hidden until after the first POS sales. The backend (`app/delivery`) and `DeliveryPage.tsx` remain for later.

# Delivery app integration (inbound orders)

RestoIQ receives delivery orders through a signed webhook. Swiggy and Zomato do not offer a public order API, so orders normally come via a partner or middleware (e.g. UrbanPiper) that is configured to POST to RestoIQ. Partner terms and fees are unverified; confirm them with the provider.

## Setup
1. Owner/manager: **Delivery apps** page -> pick provider -> *Create connection*.
2. Copy the **webhook URL** and **secret** (shown once).
3. Configure the middleware to POST JSON to the URL, signing the raw body with HMAC-SHA256 using the secret in header `X-Signature` (optional `sha256=` prefix).

If the middleware's payload differs from the format below, a small adapter is needed; this format is our own canonical design, not an official Swiggy/Zomato/UrbanPiper schema.

## Payload
```json
{
  "event": "order.created",
  "external_order_id": "SW-1001",
  "customer": {"name": "Ravi", "phone": "9999999999"},
  "delivery_address": "Madhapur",
  "items": [{"sku": "FD-014", "name": "Aloo Paratha", "quantity": 2, "unit_price": 150}],
  "total": 315, "commission": 60, "payment": "prepaid", "notes": ""
}
```
`event` is `order.created` or `order.cancelled`. `unit_price` is treated as pre-tax; if absent the menu price is used.

```bash
BODY='{"event":"order.created","external_order_id":"X1","items":[{"sku":"FD-014","name":"x","quantity":1}],"payment":"cod"}'
SIG=$(printf '%s' "$BODY" | openssl dgst -sha256 -hmac "$SECRET" | awk '{print $2}')
curl -X POST "$WEBHOOK_URL" -H "X-Signature: $SIG" -H "Content-Type: application/json" -d "$BODY"
```

## Behaviour
- Replays of the same `external_order_id` are idempotent (`duplicate: true`).
- Items match by SKU, then name. Unmatched items -> status `needs_mapping`, a manager task is raised, and the manager maps them on the page; the order is then created.
- Matched orders become delivery orders (source = provider) in the kitchen, with a kitchen task. Prepaid orders get a payment recorded under the provider name.
- If the aggregator total differs from our computed total by more than Rs 1, the order is flagged *total mismatch*.
- `order.cancelled` cancels the order unless it is already completed or paid.
- Summary shows gross, commission and net per provider.

## Limitations
- No outbound sync: accept/reject, status updates, menu or stock push to the aggregator are not implemented.
- Verified only with simulated payloads, not with live Swiggy/Zomato/UrbanPiper traffic.

## Integration engine (adapters)
Each provider is an adapter in `backend/app/delivery/adapters.py` with two jobs: `verify()` the request and `parse()` its payload into the canonical order. Matching, order creation, kitchen tasks, idempotency and reporting are shared. `GET /api/v1/delivery/providers` lists adapters and their capabilities.

Currently Swiggy, Zomato and UrbanPiper all use the canonical adapter, because their real payloads, signing schemes and credentials need partner onboarding that has not happened. When access is granted, add a subclass with the provider's documented parser and register it in `PROVIDERS`.

Not yet part of the engine: outbound sync (order accept/reject, status, menu/stock push) and non-delivery apps (Razorpay orders, Tally export, WhatsApp). Each would be a separate adapter type on the same pattern, and each depends on that service's API, permissions and terms.
