# Restaurant Signup & Onboarding Runbook

Operator guide for onboarding a new restaurant onto RestoIQ. Steps marked **[Self-serve]** are done by the restaurant in the app, **[You]** by the platform team (platform admin login), and **[Manual]** means there is no UI/API yet and engineering must do it.

## How RestoIQ helps the restaurant (use this in sales calls)
| Problem today | What RestoIQ does | Status |
|---|---|---|
| Owner can't see which tables are really occupied or idle | Cameras watch every table; **Live floor** shows *people seated / empty / no signal* per table, refreshed every few seconds | Built; accuracy not yet validated on real footage |
| Tables stay dirty or unattended after guests leave or arrive | Cameras create staff tasks by themselves: *guests seated → waiter greets*, *guests left → cleaner resets table* (table status follows). **No POS needed.** A POS adds order/food-ready/bill tasks on top | Built (camera tasks are advisory until accuracy is validated) |
| Kitchen, waiters and cleaners are not coordinated | Role-based screens: Kitchen, Staff tasks, Native POS; each login sees only its role | Built |
| No view of table turnaround and idle time | Per-table occupancy history from cameras | Weekly/monthly report includes table usage (camera data, unvalidated) |
| Revenue leakage / low table utilisation | Sales analytics and menu recommendations (from our POS data) | Built |
| Many outlets, no central control | One owner login, outlet switcher, staff per outlet | Built |

One plan: **RestoIQ POS, ₹499 per outlet per month or ₹5,999 per outlet per year**, excluding GST, first month free. It includes the complete POS, camera table monitoring, staff tasks and revenue reports. No external POS integration exists.

**Say plainly to every restaurant:** camera detection is a new feature that has not yet been validated on real restaurant footage. Offer the free month as a pilot and measure accuracy together.

## 0. One-time platform setup
1. Set strong values in `.env`: `JWT_SECRET`, `CAMERA_ENCRYPTION_KEY`, `VISION_API_KEY`, `DEMO_ADMIN_PASSWORD`, `PLATFORM_ADMIN_EMAIL`, `PLATFORM_ADMIN_PASSWORD`; set `COOKIE_SECURE=true` and `ENVIRONMENT=production` behind HTTPS.
   `VISION_API_KEY` is now required (compose refuses to start without it): use 32+ random characters. Any `ENVIRONMENT` other than `development` enforces strong secrets and `COOKIE_SECURE=true`, hides `/docs` and never seeds demo accounts. Login is rate limited (8 wrong passwords per account, 40 per address, per 15 minutes) and `/api/v1/internal/` is blocked at nginx. Camera addresses pointing at localhost, link-local or our own services are rejected.
2. `docker compose up --build -d` (runs migrations and seeds the platform admin).
3. Sign in at `/` as the platform admin. You land on **Platform admin** (restaurants, invoices, plans & pricing).
4. Confirm prices under **Plans & pricing** (set your own monthly and yearly price per outlet and the GST %; the landing page and billing read them). The landing page reads these prices.

### Sales demo restaurant
Run `docker compose exec -T -e PYTHONPATH=/app api python -m app.demo_restaurant --password 'YourDemoPass1'` (works in production). It creates `demo@restoiq.in` with a Hyderabad outlet, 30 menu items, 12 tables, about 70 paid orders over a month (cash, UPI, card), 5 customers, staff logins (`cashier@`, `server@`, `kitchen@`, `cleaner@demo.restoiq.in`), stock and staff tasks. Re-running is safe and adds nothing twice; add `--reset-password` to change the password.

## 1. Collect from the restaurant before signup
| Area | Data |
|---|---|
| Owner | Name, mobile (10-digit Indian, starts 6-9), email |
| Business | Restaurant name, address, city, state (2-letter code, e.g. TS), pincode, GSTIN (optional) |
| Outlets | Count, names, opening hours, number of floors |
| Tables | Per floor: count, table numbers exactly as on the floor, seats |
| Menu | Items, categories, prices, GST rates |
| Staff | Name, email, role, outlets |
| Baselines | Peak hours, average bill, table turnaround time, festival/closed days |
| Legal | Written CCTV consent, customer notice at premises, billing contact |

### 1a. Camera details to ask for (per floor)
| Ask | Why |
|---|---|
| How many floors, and how many cameras on each? | Each floor needs enough cameras so every table is visible in at least one |
| Camera brand/model and whether it is **IP/ONVIF with RTSP** (Hikvision, Dahua, CP Plus, etc.) | Live detection needs an RTSP stream. Analog cameras need a DVR/NVR that exposes RTSP |
| Is RTSP enabled? RTSP URL, port, username, password | e.g. `rtsp://user:pass@192.168.1.10:554/Streaming/Channels/101` (Hikvision) or `.../cam/realmonitor?channel=1&subtype=1` (Dahua). Use a **read-only viewer account**, and the sub-stream (lower resolution) |
| Is the stream reachable from the internet / our server? | Our server must reach the camera. Options: VPN/site-to-site, port-forward with a strong password, or a small on-premise gateway. Never expose cameras without a strong password |
| Upload bandwidth at the restaurant | Sub-stream ≈ 0.5-2 Mbps per camera. Our server pulls it continuously |
| Mounting: height, angle, lighting at night | Overhead/angled views work best; tables must not be hidden behind pillars; people must be visible in the table area |
| Which table numbers does each camera see? | Needed to draw zones; one table can be seen by several cameras |
| A sample screenshot or 10-minute clip per camera | Used for drawing zones and for validating accuracy |
| Written consent and signage | Legal requirement before streaming CCTV |

If the restaurant has **no RTSP-capable cameras**: they can buy one IP camera per floor area (typically ₹2,500-6,000 each) or upgrade the DVR. As a fallback, upload recorded clips (`recording` source) for a pilot; this is not live.

## 2. Signup **[Self-serve]**
1. Owner opens the site, picks monthly or yearly billing and clicks **Start your free month** (`/signup?cycle=...`).
2. Fills owner, restaurant, address and password; submits.
3. The system creates the organization, owner login, first outlet, subscription in **trial** for 30 days, and signs the owner in.
4. Owner sees the Overview dashboard with a "Free trial: N days left" banner.

Verify as platform admin: the restaurant appears in **Restaurants** with status `trial` and an end date.

> Email/SMS verification is not implemented; the owner's email is trusted as typed. Check details by phone.

## 3. Staff & roles **[Self-serve]**
Owner → **Staff & access** → add each person (name, email, role, outlets, temporary password). Roles: manager, cashier, waiter, kitchen, cleaner, analyst. Only the owner can create managers. Use **Edit** to change role, outlets or reset password; the toggle deactivates a login. Staff sign in from the same sign-in popup and see only their role's screens.

## 4. Tables and floor **[Self-serve]**
Owner/manager → **Tables & floor** (select the outlet in the header first). Use **Add many tables at once** (prefix, count, seats, floor name → T01, T02, …) or **Add one table**; edit seats inline or remove a table. Names should match the physical table numbers because cameras and tasks refer to them. Tables with order or task history cannot be deleted. Limit: 200 tables per outlet.

## 5. Our POS
1. Menu: owner/manager adds categories and items (use **Importing your menu** below to load many items from Excel/CSV).
2. Tables must exist (step 4).
3. Staff use **Native POS**, **Kitchen** and **Staff tasks**.

## 7. Cameras and AI monitoring
Step by step for one outlet (about 30-60 minutes):
1. Obtain written CCTV consent and display a notice to customers.
2. Collect the details in section 1a and confirm the stream plays (open the RTSP URL in VLC from a machine on the same network, then from our server).
3. In the app, as owner: **Tables & floor** → create all tables per floor first.
4. **AI monitoring** → **Add camera**: name, **floor**, RTSP URL (stored encrypted, never shown again). Repeat for every camera; several cameras per floor are expected.
5. Per camera, **Table zones**: upload a screenshot of that camera's view, outline each table it can see, **Save zones**.
6. Check the per-floor panel: it must read *all tables covered*. Fix any listed uncovered table by adding a camera or zone.
7. Wait ~30 s, open **Live floor**: sit a person at a table and confirm *AI: people seated* appears after ~5 s and clears ~10 s after they leave.
8. Pilot: compare AI with staff observation for a few service days before presenting numbers to the owner.

API alternative for step 4: `POST /api/v1/outlets/{outlet_id}/cameras` with `restaurant_id`, `name`, `source_type` (`rtsp` or `recording`), `stream_url`, `floor_id`.

Details:
3. Draw table zones **[Self-serve]**: Owner/manager → **AI monitoring** → **Add camera** (name, RTSP URL or recorded video), then **Table zones** on the camera card. Upload a screenshot of the camera view (JPG/PNG, max 8 MB), pick a table, click 3+ corners around it, **Finish zone**, repeat for every table, then **Save zones**. Each table gets one zone per camera; crossing or tiny zones are rejected. (API: `PATCH /outlets/{id}/cameras/{camera_id}/regions`, polygon points normalized 0–1.)
3a. **Cameras are per floor.** Pick the floor when adding a camera and add as many cameras per floor as needed so every table is visible. A camera's zones may only use tables on its floor; the AI monitoring page shows, per floor, how many tables are covered and lists uncovered ones. A table may be outlined in several cameras where views overlap.
3b. **Owner setup guide.** After signup the owner lands on **Setup guide** (also in the menu): tables → cameras → table zones → menu → staff logins. Progress is computed from real data (`GET /outlets/{id}/onboarding`).
4. **Live detection (`vision` service).** The `vision` container reads every enabled camera that has table zones (RTSP, or the uploaded recording looped), detects people with YOLOv8n on CPU (~1 frame/s per camera), keeps a per-camera 5 s enter / 10 s leave hysteresis per table, then fuses all cameras of the outlet: a table is *occupied* if any camera sees a person in its zone. Tables with no working camera show *no signal*, never *empty*. It posts `TABLE_OCCUPIED` / `TABLE_FREE` / `TABLE_UNKNOWN` observations; **Live floor** shows them as an "AI" tag next to the POS status. New or changed cameras are picked up within 30 s. The server must be able to reach the camera RTSP address. Observations stay `unvalidated`, but they drive staff work with no POS: a free→occupied change creates a *greet guests* task (waiter) and sets a FREE/READY table to OCCUPIED; occupied→free creates a *clean table* task (cleaning) and sets an OCCUPIED/BILLING table to DIRTY. Completing the cleaning task resets the table. At most one open task of each type per table; the first sighting after start-up or an outage never creates tasks. Verified so far only on a still-image test video; before promising accuracy, record 2-3 days of real footage, compare with staff counts and tune (camera angle, `VISION_CONFIDENCE`, zone shapes).

## 8. Go-live checklist
- [ ] Owner can sign in and see the dashboard
- [ ] Staff logins created and tested per role
- [ ] Tables exist and match the physical floor
- [ ] Menu loaded and spot-checked; printers tested (see ONBOARDING_CHECKLIST.md)
- [ ] Optional: cameras alone already drive greet and cleaning tasks
- [ ] Cameras registered, zones drawn, footage validated
- [ ] Consent and privacy notice in place
- [ ] Billing contact and GSTIN recorded

## 9. Billing and trial **[You]**
1. Day 0: trial starts automatically (30 days). Platform admin → **Restaurants** shows the status.
2. At expiry the restaurant is locked out (API returns 402, owner sees "Your free trial has ended"). Use **+7 days trial** to extend or **Activate** to convert.
3. Normally the owner pays or sets up auto-renew themselves under **Subscription** (see below). Manual fallback: **Restaurants → Create invoice** (price × outlets + GST; refused during trial) for customers who pay by bank transfer.
4. For a manual payment, **Invoices → Mark paid** activates a trial restaurant. **Void** cancels a pending invoice.
5. Change prices under **Plans & pricing**; new invoices use the new price.

## Known gaps
Email/SMS verification of new accounts, direct Swiggy/Zomato integration (UrbanPiper adapter exists, untested live), on-premise POS agent, on-premise POS agent, LLM-written report narratives (reports use fixed rules, no LLM is configured), email delivery of reports (they are generated automatically every Monday and on the 1st at 07:00 IST and shown on the Reports page), and accuracy validation on real footage are not implemented. The camera zone editor and the live detection worker are implemented (section 7).

## Menu, prices and GST

Owners and managers use **Menu & GST** to add categories and items, set prices (excluding GST), choose a GST rate per item (0/5/12/18/28%), and mark items unavailable. Bill numbers are consecutive per outlet and financial year (e.g. `O13/2627/000001`). Bills split GST into CGST and SGST and show the restaurant GSTIN if it was entered at signup. Choose *Regular* or *Composition* scheme; composition outlets bill 0% tax with the composition notice.

Since 22 Sep 2025 standalone restaurants charge 5% GST without input tax credit (hotel restaurants in rooms of ₹7,500+ per night charge 18%). This came from web summaries, so **have the restaurant's accountant confirm the rate and scheme**.

GST report: the GST report page lists paid bills by day and GST rate (CGST/SGST) with CSV download. Discounts and service charge are apportioned across GST rates (taxable value is after discount, including service charge), but partial refunds are not netted, so the accountant must verify before filing.

Order flow: Orders & billing and Kitchen pages move an order from kitchen to table, take cash/UPI/card payments (recorded only; we do not process them, split payments allowed) and release the table.

Running orders: on Orders & billing, "Add items" sends extra items to the kitchen as KOT 2, 3… (with per-item notes); owner, manager or cashier can cancel an item with a reason. Totals and the bill recalculate, cancelled items are excluded from the bill and GST report, and a cancel is refused if payments already exceed the new total. Adding items after "bill requested" reopens the order for the kitchen. Cancelling the last item cancels the order and frees the table.

Discount, service charge, tip, round-off: Orders & billing → "Discount / tip" (owner, manager, cashier). A percent or fixed discount needs a reason; it reduces the taxable value, so GST is charged on the discounted amount per rate. Menu → "Service charge & round-off" sets the outlet's service-charge percent (taxed at the items' GST rates, can be waived per bill) and optional rounding to the rupee, shown on the bill. Tips are separate, untaxed, added to the amount payable and excluded from revenue and the GST report. Settings apply to bills created or changed afterwards. Coupon codes are not built.

Still missing versus established POS products: coupon codes, recipe-level inventory, direct Swiggy/Zomato menu/stock sync.

## Importing your menu

On **Menu & GST**, "Import menu from Excel or CSV" loads many items at once. Download the template first. Columns: `category`, `name`, `code` (optional), `price` (excl. GST, ₹ and commas allowed), `gst` (0/5/12/18/28; blank = 5), `sizes`, `addons`. Sizes and add-ons use `Half=120;Full=200`.

- The upload is previewed first. If any row has an error, nothing is saved; fix the file and upload again.
- Existing items are matched by code, then by name (case-insensitive) and get their price, GST, name and category updated. Listed sizes/add-ons are added or updated; unlisted ones are not removed. Blank codes on new items are auto-generated (`M001`…).
- Limits: 2 MB, 1000 rows, .csv or .xlsx.
- Item names can be edited inline. An item can be deleted only if it was never sold; otherwise switch it to unavailable.

## Printing KOTs and bills
- **Print KOT**: Orders page (expand an order) or Kitchen page, one button per KOT. **Print** on a bill uses a thermal layout; pick 80 mm or 58 mm paper in the bill window (remembered per browser).
- Printing uses the browser's print dialog, so a thermal printer must be installed as a normal printer on that device. Choose it in the dialog and turn off headers/footers. Silent auto-print and ESC/POS printers (network or Bluetooth) are not built.

## Sizes (variants) and add-ons

In **Menu → Sizes & add-ons** per item: a *size* (Half/Full) replaces the item price; an *add-on* (Extra cheese) is added on top. If an item has sizes, one must be chosen when ordering. The name, size and add-ons are saved on the order line, so later menu edits never change old bills. Reports list each size as its own item name (e.g. "Biryani (Half)").

## Quick item search and split payment

- **POS screen:** type part of an item name or its SKU (use short SKUs like `BR1` as short codes) to filter the menu. Press Enter on an exact SKU to add that item (opens the size/add-on picker if it has options).
- **Split payment:** in *Take payment*, enter the number of people to fill each person's share, and record one payment per person, each with its own method. This is a split of one bill and one GST invoice, not separate invoices per person.

## Takeaway and delivery orders

On the POS screen choose **Dine-in / Takeaway / Delivery**. Takeaway and delivery need no table; delivery requires the customer's phone and address. Orders go to the kitchen like any other, show a type tag in Orders and Kitchen, and the name/phone/address print on the KOT and bill. Orders move *Ready → Handed over* (takeaway) or *Ready → Out for delivery → Delivered* (delivery), then take payment (cash on delivery works the same way).

Delivery or packing charges are not a separate field: add them as a menu item (e.g. "Delivery charge") with the right GST rate, so tax is calculated correctly. Swiggy/Zomato orders can arrive automatically through UrbanPiper (Settings > Integrations, see INTEGRATION_ENGINE.md); without a connection, enter them by hand.

## Working when the internet drops

RestoIQ can be installed on a tablet or PC (browser menu → *Install app*). Open it once online so it can save itself on the device.

- **Offline you can:** open the app, take **new orders** (dine-in, takeaway, delivery), print a **provisional bill** and note **payment received** (cash/UPI/card). Orders are saved on the device and sent to the kitchen when the internet returns. The offline total uses the same GST, service charge and round-off rules as the server.
- **Provisional bill:** it is marked "Not a tax invoice" and has no bill number. The numbered GST bill is issued once online (reprint it from Orders → Bill).
- **Offline payments** are recorded on the order once it is marked handed over / delivered, so the kitchen keeps seeing the order until then.
- **Offline you cannot:** print numbered GST bills, see the kitchen or other devices' orders, or change the menu. If the server rejects a saved order or payment (e.g. the table was taken, or prices changed) it is shown in red so you can fix it by hand.
- Keep a mobile hotspot as backup for payments and bills. Sign out clears the saved data from the device.

## Paying for your RestoIQ subscription

Owners open **Subscription** in the menu, pick monthly or yearly and pay with UPI, card or netbanking through Razorpay. Paying during the free trial does not waste trial days: the paid period starts when the trial ends. This payment is only for the RestoIQ plan; your customers' bills are still recorded in the POS.

- **Auto-renew (recommended).** The owner chooses *Subscribe with auto-renew* and approves a UPI AutoPay, card or netbanking mandate once. Razorpay charges it every month or year; each charge creates a paid invoice and an email receipt. The first charge happens when the free trial or current period ends, so no trial day is lost. The owner can cancel at any time on the Subscription page and the plan stays active until its end date.
- **Price lock.** The amount is fixed when the owner subscribes (price × outlets + GST at that moment). If you later change the price in Plans & pricing, existing auto-renewals keep the old amount; to move a customer to the new price they cancel and subscribe again. Adding outlets later also needs a re-subscribe.
- **Failed auto-charge.** Razorpay retries; if it gives up the subscription shows "halted", the owner sees a warning and the 3-day grace period then lock apply as before.
- **Pay once (no auto-renew).** Still available: one payment per period, with a "renews in N days" banner and Renew button. Renewal reminder emails are not sent to owners who have auto-renew on.
- **Grace period.** After the paid period ends the workspace keeps working for 3 days, then locks. The owner sees the payment page instead; other staff are told to ask the owner. Data is kept and access returns right after payment.
- **Tax invoice.** Every paid invoice has an **Invoice** button on the Subscription page that prints an A4 GST invoice (CGST+SGST within the seller's state, IGST otherwise).
- **Policies.** Terms, Privacy and Refund pages are at `/legal/terms`, `/legal/privacy` and `/legal/refund`, linked from the landing footer, and signup requires accepting them.

### Setting up payments and invoices (RestoIQ operator)

Put these in `.env` (see `.env.example`) and restart the api:

| Variable | Purpose |
|---|---|
| `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET` | Razorpay keys. Use `rzp_test_` keys until your account is activated, then live keys. |
| `RAZORPAY_WEBHOOK_SECRET` | Same value as in Razorpay Dashboard > Webhooks (URL `https://YOUR-DOMAIN/api/v1/billing/webhook`). Tick `payment.captured`, `subscription.authenticated`, `subscription.activated`, `subscription.charged`, `subscription.halted`, `subscription.cancelled` and `subscription.completed`. Auto-renew charges are only recorded through this webhook, so it is required for auto-renew. Subscriptions must be enabled on your Razorpay account (Dashboard > Subscriptions). |
| `SELLER_LEGAL_NAME`, `SELLER_GSTIN`, `SELLER_ADDRESS`, `SELLER_STATE_CODE`, `SELLER_SAC` | Your business details on invoices. While blank, invoices are marked DRAFT (a receipt, not a tax invoice). Confirm the SAC code and 18% rate with your accountant. |

Before launch also replace the placeholders (`[Your legal business name]`, `[support email]`) at the top of `frontend/src/features/legal/LegalPage.tsx` and have a lawyer review the three policy pages; they are drafts.

## Email and password reset

- **Forgot password:** the sign-in form has a "Forgot password?" link. We email a one-time link that expires in 60 minutes; opening it lets the user choose a new password. The reply is the same whether or not the address is registered.
- **Emails we send:** welcome (on signup), password reset, payment receipt (after each subscription payment) and renewal reminders to the owner 7, 3 and 1 day before the trial or plan ends (a daily job at 10:00 IST).
- **Operator setup:** set `RESEND_API_KEY` (or `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`), `MAIL_FROM` (a sender on a domain verified in Resend, for example `RestoIQ <no-reply@yourdomain.com>`) and `APP_PUBLIC_URL` (the public web address used in links) in `.env`, then restart the api, worker and beat. Until `MAIL_FROM` is set, notification emails are skipped and "Forgot password" says it is unavailable.

## Platform admin: restaurants, dues and reminders **[You]**

Sign in as the platform admin. The page shows how many restaurants are paying, on trial or overdue, the amount collected and due, and for each restaurant the plan end date, total paid, amount due and reminders sent.

- **Pricing:** *Plans & pricing* sets the monthly price, yearly price and GST. The landing page, signup page, legal pages and new invoices all use this price. Pending invoices keep their old price.
- **Reminders:** emailed automatically to the owner 7, 3 and 1 day before the plan or trial ends. *Send reminder* sends one now (also for overdue accounts). Every send is listed under *Reminder log*, with a "email not set up" result if `MAIL_FROM`/`RESEND_API_KEY` are missing.
- **Overdue:** after the plan ends there are 3 grace days, then the account locks until the owner pays. *+7 days* gives extra time.

## Order details, customers, and day close

- **Order details (POS):** enter *covers* (guests) for dine-in, an order note for the kitchen, and tap quick notes ("Less spicy", "No onion"…). The waiter's name is stamped automatically and shown on the Orders page.
- **Customers:** entering a phone number on an order creates or links a customer automatically (matched on the last 10 digits). Open *Customers* to search, edit birthday, anniversary, GSTIN, address, and see order history.
- **Day close & cash:** each day, record petty cash paid out/in, then count the drawer and close the day. Opening cash for the next day is the previous day's counted cash. Enter opening cash only on the very first day. A difference needs a note; a closed day cannot be edited. Owner, manager, and cashier can use this page; only owner/manager can delete petty-cash entries.

## Tables and running orders

- **Live floor:** each table card shows the running amount, minutes seated, waiter and guests. Search by table name, filter All / Free / Running / Bill printed, and filter by waiter.
- **Shift table / Merge** (Orders page): move a running dine-in order to a free table, or merge it into another running order (items move over, the other order is closed). Merge is blocked if either order already has a payment.
- **Orders filters:** search by bill number, customer or table; filter by status, order type and staff.
- **Split payment:** record several payments (cash + card, etc.) against one bill until it is fully paid.

## Complimentary bills, customer account, advance orders, sales summary
- **Complimentary / non-chargeable:** on **Orders**, click *Complimentary*, tick the free items (all of them for a non-chargeable bill) and give a reason. Free items print at 0.00 and are excluded from tax. Not possible after a payment is recorded.
- **Void:** managers can void an open order with a reason. Blocked once any payment, including an advance, exists.
- **Split payment:** record several payments on one bill; quick buttons fill the exact or common amounts.
- **Customer account (pay later):** the order needs a customer phone. Choose *Customer account* as the method; the amount is added to the customer's balance. On **Customers**, record money received or a manual charge. Bills paid on account cannot be refunded.
- **Advance orders:** for takeaway/delivery, set a pickup time and optional advance amount in the POS. They show in the *Today's advance orders* strip on Orders. Limitation: the order reaches the kitchen immediately; there is no timed hold.
- **Petty cash:** each entry has a category and pay method; only cash entries change the drawer.
- **Day close:** blocked until every order of the day is paid or voided (the page lists them with a Void button).
- **Sales summary:** a report for any date range with totals, payment method, order type and item category, and a Print button.
- Not available: e-bill sharing, Razorpay/UPI QR inside the POS, table bookings.

## Exceptions report and daily matching (owner)

**Exceptions** (owner/manager, left menu) lists voided bills, cancelled items, discounts, complimentary items and refunds with who did them and why. Review it weekly; one person with unusually high counts is worth a conversation. Reprints are not tracked.

**Daily matching** (end of day):
1. Sales summary: note Cash, Card and UPI totals for the day.
2. Cash: Day close compares counted cash with expected cash.
3. Card: compare with the card machine's day-end batch report.
4. UPI: compare with the UPI app or machine transaction list.
5. Weekly: card/UPI settlements appear in the bank statement a day or two later, less fees.

RestoIQ records payments; it does not collect them. A mismatch with the machine or bank means a payment was recorded wrongly, a swipe was not entered, or a bill was never created.
