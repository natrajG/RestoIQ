# Restaurant POS & Operations Intelligence

Multi-tenant restaurant platform with a first-party POS, optional existing-POS connectors, kitchen and floor operations, inventory, customer loyalty, workforce/payroll inputs, sales analytics, and an independently testable camera-analysis service.

The backend is **FastAPI/Python**. Workers use Celery + Redis. Data is stored in PostgreSQL with Alembic migrations and tenant row-level security. The web app uses React, TypeScript, Ant Design, and ECharts.

## Product and plan

RestoIQ is a complete restaurant POS (menu, GST billing, KOT, payments) with live CCTV table monitoring, role-based staff tasks and revenue reports. There is no external-POS integration: the built-in POS is the only transaction source.

There is a single plan, `RESTOIQ_POS`: ₹499 per outlet per month or ₹5,999 per outlet per year, excluding GST, with the first month free.

The web app uses one role-filtered navigation shell. Native transactions, AI operations and administration have separate feature folders, API clients and backend packages. Camera/LLM processing remains optional and must not be required for billing.

Payments can be recorded by method/status, but live card/UPI gateway or terminal processing is not included in this initial release.
Native payment and refund requests require an `Idempotency-Key` header. Replays with the same payload return the original financial record; reusing a key with a different payload is rejected.

Menu intelligence recommendations currently use historical order behavior by **day of week**, **meal window**, and configured **festival calendar** entries for each tenant/outlet. Season and weather signals are intentionally not included yet and should only be added after measured forecast uplift.

## Start the demo

Requirements: Docker Engine and Docker Compose.

```bash
cp .env.example .env
# Set distinct random POSTGRES_ADMIN_PASSWORD, POSTGRES_APP_PASSWORD, JWT_SECRET,
# CAMERA_ENCRYPTION_KEY value in .env.
# DATABASE_URL and MIGRATION_DATABASE_URL must use the matching DB passwords.
docker compose up --build
```

Open `http://localhost:8180`. Demo login defaults are `admin@demo.local` / `change-me-before-sharing`; change them in `.env` before exposing or sharing the deployment. API docs are at `http://localhost:8181/docs`. PostgreSQL is bound to localhost port 55433; Redis is internal to Compose.

The seeded demo contains one tenant, one restaurant, 12 tables, sample menu items, and synthetic records. Demo content is not actual customer or restaurant data.

## India launch and compliance

Restaurant defaults use INR and `Asia/Kolkata`. Tax and payroll components are configurable inputs; this software does not assert statutory compliance. GST and applicable PF/ESI/TDS calculations and any production payroll exports must be reviewed and approved by an India-based accountant for the applicable state, entity, and employee circumstances before use. Salary disbursement is not implemented.

## Video and privacy

The backend currently supports camera configuration, encrypted stream credentials, region metadata and explicitly unvalidated observation ingestion; a `vision` worker (YOLOv8n person detection, per-camera hysteresis, multi-camera fusion per outlet) and a table-zone editor are implemented, but accuracy has not been validated on real restaurant footage. Do not treat synthetic events or configured cameras as evidence of working occupancy detection. The occupancy reference review identified useful next behaviors: per-table enter/leave hysteresis, confidence filtering, polygon validation, reconnect/outage-aware monitoring, latest-frame processing and recorded-video regression tests.

The feature review used [Restaurant-Table-Occupancy-Detection](https://github.com/sanaulislamzihad/Restaurant-Table-Occupancy-Detection), which is MIT-licensed. Its concepts are being adapted to the existing multi-tenant PostgreSQL/event architecture; no source files have been copied. Detector-suggested table outlines remain deferred until a suitable model and actual-restaurant validation are available. Facial recognition is not implemented. Camera credentials are encrypted at rest; configure a distinct `CAMERA_ENCRYPTION_KEY`. Set the retention period with `VIDEO_RETENTION_DAYS`.

## Service layout

| Path | Purpose |
|---|---|
| `backend/app/core` | Shared configuration, persistence, security primitives and infrastructure |
| `backend/app/{auth,pos,reports,ai_operations,inventory,workforce}` | Feature-owned routes, schemas, services, repositories and business rules |
| `backend/alembic` | Versioned schema and PostgreSQL tenant RLS migration |
| `vision` | Live table-occupancy worker (CPU YOLOv8n); reads cameras, reports unvalidated observations to the API |
| `frontend/src/features` | React/TypeScript feature pages, API clients and role-aware application shell |
| `docker-compose.yml` | Local multi-service stack |

## Architecture and flow documentation

- End-to-end flow: `docs/END_TO_END_FLOW.md`
- Architecture diagram (PNG): `docs/architecture/restaurant-platform-architecture.png`
- Hyderabad owner demo script: `docs/HYDERABAD_DEMO_WALKTHROUGH.md`

## Security and operations notes

- Production requires unique secret values, HTTPS termination, restricted network access, managed secret storage, backups, and monitoring.
- Tenant-owned data tables enforce PostgreSQL row-level security; API transactions set the authenticated tenant context. - JWTs are held in `HttpOnly`, `SameSite=Strict` cookies. No default facial recognition or public camera endpoints are enabled.
- Provide camera connectivity and representative footage, jurisdiction-specific compliance review, retention/privacy policy, and target deployment details before production integration.

## Development checks

Backend tests: `docker compose exec api pytest`  
Frontend build/type-check: `cd frontend && npm ci && npm run build`  
Inspect service logs: `docker compose logs -f api worker`
