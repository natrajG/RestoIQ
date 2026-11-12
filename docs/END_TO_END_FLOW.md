# End-to-End Flow (Architecture + Runtime)

This document describes the current production-oriented flow for the restaurant platform on the single `RESTOIQ_POS` plan (native POS + operations intelligence; ₹499/month or ₹5,999/year per outlet).

## 1) Tenant and outlet setup

1. Organization is created (`organizations`).
2. A `RESTOIQ_POS` subscription is created with a billing cycle (`monthly` or `yearly`), starting in a free trial.
3. Floors/tables/cameras/staff are configured (`floors`, `dining_tables`, `cameras`, `employees`, `outlet_memberships`).

## 2) Authentication and tenant isolation

1. User signs in to FastAPI (`/api/v1/auth/login`) and receives `HttpOnly` session cookie.
2. Every request resolves principal (`auth/dependencies.py`) and sets PostgreSQL tenant context (`set_tenant_context`).
3. PostgreSQL RLS policies enforce tenant boundaries on tenant-owned tables.

## 3) Transaction source flows

## 3.1 Native POS flow (`pos_mode = built_in`)

1. Frontend creates order (`POST /api/v1/outlets/{id}/orders`) with idempotency key.
2. Backend writes `orders` + `order_items`, computes totals, emits normalized operational event (`operational_events`), and creates kitchen task.
3. Staff updates order events (`FOOD_READY`, `BILL_REQUESTED`, etc.).
4. Payment/refund is recorded with required `Idempotency-Key`:
   - `POST /orders/{id}/payments`
   - `POST /orders/{id}/refunds`
5. Financial events are persisted and normalized events are emitted for analytics/tasking.

## 4) Operations intelligence flow

1. Cameras are configured with outlet-specific table polygons.
2. Observation ingestion records low-level camera observations.
3. Task workflows:
   - `pending -> acknowledged -> completed`
   - completion events update table/order states when applicable.
4. Recommendation endpoint combines:
   - live cleaning bottlenecks (dirty tables/open cleaning tasks)
   - menu demand intelligence using historical order behavior by day-of-week + meal window + active festivals

## 5) Menu intelligence (current scope)

Current signal inputs:

- day-of-week
- meal window (breakfast/lunch/snacks/dinner/late-night)
- tenant/outlet festival calendar (`festival_calendar`)

Current exclusions by design:

- weather/climate
- seasonality models

Those are intentionally deferred until measurable uplift is proven.

## 6) Frontend request flow

1. React app calls `/api/v1/*` via shared API client with credential cookies.
2. Role-based AppShell controls navigation visibility.
3. Feature pages:
   - Dashboard (live tables/tasks/cameras)
   - Native POS
   - Analytics
   - Staff tasks
   - Settings (plan + POS mode)

## 7) Reliability and background processing boundaries

- POS ordering and billing run without dependency on camera/LLM availability.
- Heavy CV/AI processing is intended for workers; billing path remains synchronous and deterministic.
- Structured events are stored in PostgreSQL for retryable downstream handling.

## 8) Key persistence objects

- Source of transactions: `orders`, `order_items`, `payments`, `refunds`
- Normalized operations stream: `operational_events`
- Operations execution: `staff_tasks`, `dining_tables`, `observations`
- Intelligence context: `festival_calendar`
- Commercial controls: `subscription_plans`, `subscriptions`
