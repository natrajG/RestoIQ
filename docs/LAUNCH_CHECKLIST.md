# RestoIQ launch checklist (owner inputs needed to resume)

Give these to the assistant to start the next session. Never paste secrets into chat; put them in `.env` and say "done".

## A. Infrastructure (needed to start `rel-8-prod-deploy`)
- [ ] Domain name (e.g. restoiq.in) and access to its DNS
- [ ] Server: provider, OS, size (suggest 4 vCPU / 8 GB, Ubuntu 22.04+), SSH access
- [ ] Where backups go (S3/Backblaze/other bucket) and who gets alerts
- [ ] Decide camera processing location (on the server, or on-site at the restaurant)

## B. `.env` values for production
- [ ] `ENVIRONMENT=production`, `COOKIE_SECURE=true`, `SEED_DEMO=false`
- [ ] `APP_PUBLIC_URL=https://<your domain>`
- [ ] Strong `JWT_SECRET`, `CAMERA_ENCRYPTION_KEY`, DB password, `VISION_API_KEY` (32+ random chars), `PLATFORM_ADMIN_PASSWORD`
- [ ] `RAZORPAY_KEY_ID` (live), `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`
- [ ] `RESEND_API_KEY`, `MAIL_FROM`, `FEEDBACK_NOTIFY_EMAIL`

## C. Third-party accounts
- [ ] Razorpay: KYC complete, Subscriptions enabled, webhook URL `https://<domain>/api/v1/billing/webhook` with 7 events ticked (see RESTAURANT_ONBOARDING.md)
- [ ] Resend: sender domain verified (SPF/DKIM)
- [ ] One real small subscription + refund test after deploy

## C2. Business decisions
- [ ] Final monthly and yearly price (set in Platform admin; existing auto-renew customers keep their locked amount)
- [ ] Support email/phone for the legal pages and landing page (replace "[support email]")
- [ ] GSTIN, lawyer review of Terms/Privacy (deferred until first customer)

## D. Pilot (needed for `rel-11-camera-pilot`)
- [ ] One friendly restaurant willing to pilot (2-3 days)
- [ ] CCTV details: brand, RTSP URL format, resolution, number of cameras per floor
- [ ] Sample footage (a few hours, busy period) to tune table detection

## E. After deploy (assistant does these)
- [ ] HTTPS, firewall, nightly DB backup + restore test, uptime monitor
- [ ] Create the sales demo: `docker compose exec -T -e PYTHONPATH=/app api python -m app.demo_restaurant --password '...'`
- [ ] Smoke test: signup, menu, order, bill, payment, subscription, email

## Not built (optional, after first customers)
e-bill / WhatsApp bill, UPI QR in POS, table bookings, multi-table orders, loyalty UI, timed hold for advance orders.

## Delivery apps (on hold until after first POS sales)
- [ ] UrbanPiper adapter is built (Settings > Integrations) but untested on a real account. When a customer needs Swiggy/Zomato: they sign up with UrbanPiper, then follow section 5 of ONBOARDING_CHECKLIST.md.
- [ ] Not built: Dispatched/Completed status, menu and stock push. Direct Swiggy/Zomato needs partner approval.

## Integrations
- [ ] Confirm the Celery worker and beat run in production (the worker had no registered tasks before this change; check `celery inspect registered`).
- [ ] Decide which provider adapters to build next and obtain official docs, sandbox credentials and approvals first (see docs/INTEGRATION_ENGINE.md).

## POS readiness (added)
- [ ] Backups: the `backup` container writes a nightly `pg_dump` to `./backups` (14 days kept, `BACKUP_KEEP_DAYS`). **Copy that folder off the server** (rclone/S3/Backblaze) — a backup on the same disk is not a backup. Restore test: `docker compose exec -T db pg_restore -U $POSTGRES_ADMIN_USER -d <empty_db> --no-owner < backups/<file>.dump` (verified once on this stack; repeat on the production server).
- [ ] Printers: KOT/bill use the browser print dialog (58/80 mm). For silent printing start Chrome with `--kiosk-printing` and set the thermal printer as default, then switch on **Auto-print KOT** on the POS screen. Test every printer model you will sell with.
- [ ] Split bill: Orders → *Split bill* moves items to a new bill on the same table (separate invoice number).
