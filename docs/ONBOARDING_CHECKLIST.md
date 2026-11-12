# New restaurant onboarding checklist

One page, tick per restaurant. Details: `RESTAURANT_ONBOARDING.md`. Mark each item Self (restaurant) or Us.

## 1. Before the visit (collect)
- [ ] Owner name, phone, email; restaurant legal + display name, address, city
- [ ] GSTIN and GST scheme (regular / composition); FSSAI number (prints on bill)
- [ ] Number of outlets, floors, tables (names/numbers, seats)
- [ ] Staff list with roles (owner, manager, cashier, waiter, kitchen)
- [ ] Menu: categories, items, prices, GST %, veg/non-veg, sizes, add-ons (Excel/CSV or photos)
- [ ] Printers: model, connection (USB/LAN/Bluetooth), count (kitchen / bill); paper size
- [ ] Devices: billing PC/tablet/phone, browser (Chrome), Wi-Fi quality
- [ ] UPI ID / QR for payments; card machine in use
- [ ] Opening hours, time zone, service charge policy, bill-number prefix wishes
- [ ] Cameras (only if monitoring plan): brand, RTSP URL per floor, router access, upload speed

## 2. Account setup (Us / Self)
- [ ] Signup done, email verified, trial/plan chosen
- [ ] Outlet created with GSTIN, address, tax scheme, timezone
- [ ] Staff accounts created with correct roles; owner changes temporary passwords
- [ ] Floors and tables created
- [ ] Menu imported; spot-check 10 items (price, GST, variants)
- [ ] Bill header/footer, logo, FSSAI and UPI details set

## 3. Hardware (Us, on site)
- [ ] Browser `--kiosk-printing` set for silent printing; test KOT and bill on each printer
- [ ] Auto-print KOT switch on; reprint and cancel slip tested
- [ ] App installed as PWA on billing device; offline test (unplug internet, bill, reconnect, sync)
- [ ] Cameras added and AI detection verified per table (monitoring plan only)

## 4. Test run before go-live (Us + manager)
- [ ] Dine-in: open table, add items, KOT prints, add item, cancel item, transfer table
- [ ] Split bill and merge tables
- [ ] Takeaway order with customer details
- [ ] Discount, GST bill, cash / UPI / card / split payment, invoice print
- [ ] Day close and Sales summary match the cash drawer
- [ ] Void and refund (manager role only)

## 5. Delivery apps (only if used)
- [ ] Without aggregator: enter Swiggy/Zomato orders manually as delivery orders
- [ ] With UrbanPiper: restaurant has an account; get Biz ID, API username/key, production API URL
- [ ] Menu SKUs equal UrbanPiper item reference IDs
- [ ] Connect in Settings > Integrations; create the Atlas webhook with header `X-Api-Token`
- [ ] Place one test order end to end (not yet verified against a real account)

## 6. Training (Us, 1-2 hours)
- [ ] Cashier: billing, payments, reprint, day close
- [ ] Waiter: tables, orders, transfers
- [ ] Kitchen: KOT screen, ready marking
- [ ] Owner: reports, reconciliation, staff, subscription payment
- [ ] Owner: daily matching of Cash/Card/UPI totals with drawer, machine and UPI app; weekly Exceptions report review
- [ ] Leave printed quick-guide and support contact

## 7. Go-live and follow-up
- [ ] First live service with us on site or on call
- [ ] Backup running (see `LAUNCH_CHECKLIST.md`); confirm off-server copy
- [ ] Day 1, day 3, day 7 check-in: errors, printer issues, missing items
- [ ] Day 7: review reports and the Exceptions report with owner; collect feedback
- [ ] Before trial ends: explain plan and payment; confirm invoice/GST details
