# Integration Engine

One place for connecting RestoIQ to outside services. Code: `backend/app/integrations/`. UI: **Integrations** in the menu (owner/admin only).

## Architecture
```
POS actions ──publish_event──▶ outbox (integration_sync_jobs) ──worker──▶ provider.execute()
Provider ──POST webhook──▶ verify ▶ store event ▶ queue job ──worker──▶ provider.handle_event()
```
- `base_provider.py` adapter contract; `registry.py` explicit allow-list (no third-party code is ever executed); `capabilities.py`; `security.py` (Fernet-encrypted credentials, token hashing); `service.py`; `router.py`; `providers/`.
- Adapters are synchronous, matching the rest of the backend (not async as in the original brief).
- Add a provider: write a subclass declaring `ProviderInfo` (capabilities, credential fields) with `verify_webhook` / `parse_webhook` / `execute`, and call `IntegrationRegistry.register()`. No core change needed.
- Menu edits call `publish_event` (price/name -> `menu.item.updated`, active flag -> `item.availability.changed`). It never raises, so a provider problem cannot block POS requests. Add new outbound events in `service.OUTBOUND`.

## Reliability and security
- Webhooks: tenant is resolved from a secret URL token (hash stored), never from the payload; provider-specific signature check; 256 KB limit; per-connection per-minute throttle (Redis); duplicates dropped by unique `(connection, external_event_id)`; stored durably then processed by the worker.
- Jobs: unique idempotency key, exponential backoff (30s doubling, max 1h), 6 attempts then dead-letter, manual retry, stale `running` jobs recovered, `SKIP LOCKED` for concurrent workers.
- Circuit breaker: 5 consecutive failures pause a connection for 5 minutes.
- Loop prevention: events originating from a connection are never echoed to it.
- Row-level security on events, jobs and mappings; connections are filtered by tenant in code.
- Credentials are encrypted, never returned by the API; disconnecting wipes them and invalidates the URL. Payloads shown in the UI mask sensitive keys.
- Audit entries use the existing audit log (`integration_*` actions).

## Provider status
| Provider | Status | What it does |
|---|---|---|
| UrbanPiper (Swiggy, Zomato via UrbanPiper) | Live, untested against a real account | Settings > Integrations. Orders in (Order Relay webhook, event 18), cancellations in (60008); Acknowledged / Food Ready / Cancelled out. Needs UrbanPiper Biz ID, API username+key, production API URL, and a webhook in Atlas with header `X-Api-Token` = the webhook token. Menu SKUs must equal UrbanPiper item reference IDs. Source: `providers/urbanpiper.py`, `tests/test_urbanpiper.py`. |
| Swiggy, Zomato direct | Coming soon | Needs partner approval. |
| Razorpay | Live, partial | Verifies and stores payment webhooks; checks API keys. Does **not** yet update bills. Not exercised against a real Razorpay account. |
| Test sandbox | Mock | Test double, visible only in development. |
| Cashfree, PhonePe, Tally, Zoho Books, WhatsApp, SMS, Shopify, WooCommerce, ONDC | Coming soon | Declared only; no code, no capabilities claimed. |

## Credentials needed
- Razorpay: Key ID, Key secret, and a webhook secret (set the same on the Razorpay webhook pointing at the URL shown after connecting).
- Swiggy/Zomato: see DELIVERY_INTEGRATION.md.

## Deviations from the brief (deliberate)
- Providers are code-registered, not a DB table (a table would let data alter trusted behaviour).
- Webhook URL is `/api/v1/integrations/webhooks/{provider}/{token}`; the token resolves the tenant securely.
- Existing audit log and Celery/Redis are reused; no new services. No separate branch table: scope is outlet or all outlets.
- Not built: OAuth token lifecycle (no OAuth provider exists yet), GraphQL/SDK/file transports, automation-rule builder UI, scheduled/incremental sync beyond manual and event-driven, field-level conflict detection (the external-id mapping table exists but no provider uses it yet), live sandbox tests, load testing.

## Tests
`backend/tests/test_integrations.py` (26 tests, DB-backed, roll back): registry, capabilities, encryption, tenant isolation (incl. RLS), webhook validation/duplicates/rate limit/size, retries, dead-letter, circuit breaker, outage recovery, stale-job recovery, publish scoping and loop prevention, rotation, disconnect/reconnect, Razorpay signature and error mapping, masking. Run inside the api container (tests are not baked into the image):
`docker cp backend/tests/test_integrations.py restaurant-platform-api-1:/tmp/ && docker compose exec api python -m pytest /tmp/test_integrations.py -p no:cacheprovider --rootdir=/app`
