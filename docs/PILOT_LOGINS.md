# Pilot restaurant logins (local testing only)

Open `http://localhost:8180`. Use a separate browser (or incognito window) per role. These are test passwords: change them (Staff & access) before using real data on a server, and don't share this file.

Restaurant: **Pilot Restaurant** (fresh, no demo data, 30-day trial). Outlet: Pilot Restaurant.

| Role | Email | Password | Use it to test |
|---|---|---|---|
| Owner | owner@pilot.local | Pilot@Owner1 | Menu & GST, tables, staff, reports, Exceptions, subscription |
| Manager | manager@pilot.local | Pilot@Manager1 | Void, refund, discounts, settings, day close |
| Cashier | cashier@pilot.local | Pilot@Cashier1 | Billing, payments (cash/card/UPI/split), print, day close |
| Waiter | waiter@pilot.local | Pilot@Waiter1 | Tables, take order, send to kitchen, mark served |
| Kitchen | kitchen@pilot.local | Pilot@Kitchen1 | Kitchen screen: accept, mark ready |
| Cleaner | cleaner@pilot.local | Pilot@Cleaner1 | Live floor and tasks (table cleaning) |

## Test order
1. Owner: add tables (Tables & floor), import or add menu with prices, set GST and UPI ID (Menu & GST).
2. Waiter: open table, add items, send to kitchen.
3. Kitchen: accept, mark ready.
4. Waiter: mark served.
5. Cashier: bill, discount, payment, print.
6. Manager: void/refund (cashier must be blocked).
7. Owner: Sales summary, Day close, Exceptions.

---

# On-site test checklist (step by step)

Tick each box. If something fails, write down: what you did, what you expected, what happened, the time, and a screenshot. Use one phone per waiter (Chrome on Android, Safari on iPhone) and the billing computer for the cashier.

## A. Before you go (at home, on Wi-Fi)
- [ ] Open the app on every phone and the billing PC, and log in with the right role.
- [ ] On each device, open **Native POS** once while online. This saves the menu and tables for offline use.
- [ ] Add the app to the home screen on the phones (browser menu → Add to Home screen).
- [ ] Owner: tables, menu, prices, GST, UPI ID and printer paper width (58 or 80 mm) are set.
- [ ] Change the test passwords in Staff & access.

## B. Set up at the restaurant
- [ ] Connect the phones to the restaurant Wi-Fi, and the printer to the same network or Bluetooth.
- [ ] Print a test KOT and a test bill. Check that the paper width fits.
- [ ] Put the router, printer and billing PC on a UPS if you have one.

## C. Normal day (online)
1. [ ] Waiter: open a table, add items, **Send to kitchen**. A KOT prints (with Auto-print KOT on).
2. [ ] Kitchen: the order appears on the kitchen screen. Accept it, then mark it ready.
3. [ ] Waiter: add more items to the same table. This must make **KOT 2** on the same bill.
4. [ ] Waiter: mark the order served.
5. [ ] Cashier: open the bill, check that GST and totals match your own calculation, take a payment (cash, UPI, card, split) and print the bill.
6. [ ] Table goes to cleaning, the cleaner marks it clean, and the table is free again.
7. [ ] Takeaway and delivery order: create one of each.
8. [ ] Table shift, merge and split bill: try each once.

## D. Several waiters at once
1. [ ] Waiters 1, 2 and 3 each take an order on **different tables at the same moment**. All three must arrive with no error.
2. [ ] Two waiters tap Send on the **same free table at the same moment**. Only one should win and the other must see "Table is not available".
3. [ ] Two waiters add items to the **same running table** at the same time. Both KOTs must appear with different numbers (KOT 2 and KOT 3).
4. [ ] Check the kitchen: nothing is missing and nothing is doubled.

## E. Internet cut (the most important test)
1. [ ] Waiter phone: turn the phone's Wi-Fi and mobile data **off** (or switch the router off).
2. [ ] The yellow banner says "You are offline. Orders are safe on this device".
3. [ ] Take a new order on a free table and send it. You see "saved on this device", and a KOT prints if the printer is reachable.
4. [ ] Close the browser fully and reopen the app while still offline. The saved order must still be listed as "Waiting for internet".
5. [ ] Add items to a running table while offline. A new KOT must print.
6. [ ] Take a cash payment offline. It is saved as "Payment received".
7. [ ] Turn the internet back on and wait up to 30 seconds. The orders move to "Sent to kitchen", and the kitchen screen shows them with a remark "Taken offline at HH:MM".
8. [ ] Count: orders taken offline = orders in the system. No order is missing and none is doubled.
9. [ ] **Two waiters offline, same table:** switch both phones offline, take an order on the same table on each, then reconnect both. You must get **one bill with two KOTs**.
10. [ ] **5-minute outage:** switch off the router for 5 minutes (as in a generator changeover). Take 3 orders on different phones, then reconnect. All 3 must arrive.
11. [ ] Switch off a phone completely while it holds an unsent order, turn it on again, and reconnect. The order must still be there and must send.
12. [ ] Log out while orders are unsent, log in again, and reconnect. The orders must still send.

## F. Power cut
1. [ ] Switch off the main power and let the generator start. Check how long the internet is down.
2. [ ] Check that the billing PC and printer come back and that you can print after the outage.
3. [ ] Check that no order or bill was lost in the changeover.

## G. Permissions (these must be blocked)
- [ ] Waiter: cannot cancel an item, apply a discount, void or refund.
- [ ] Kitchen and Cleaner: cannot create an order, add items or take a payment.
- [ ] Cashier: can discount and cancel an item, but cannot void or refund.
- [ ] Manager: can void and refund.
- [ ] Owner: can see everything (reports, staff, subscription).

## H. Money and reports
- [ ] The bill number is in sequence with no gaps or duplicates (check 10 bills).
- [ ] Discount, service charge, GST and round-off are correct on 3 different bills.
- [ ] Split payment (e.g. half cash, half UPI) adds up to the bill total.
- [ ] Owner: Sales summary matches the total of the bills you made.
- [ ] Day close: cash counted equals cash expected (check the difference).
- [ ] Exceptions: voids, refunds and discounts appear in the log.

## I. Speed and real use
- [ ] Time one order from tap to KOT print. Note it, and note if any waiter has to wait.
- [ ] Run a busy period with every waiter working. Note any slow screens or freezes.
- [ ] Ask each waiter what is confusing or slow. Write it down.

## J. Things to write down for me
- Phone models and browsers used, and the Wi-Fi quality in each floor area.
- Printer model, how it is connected, and whether offline printing worked.
- How long the internet was down during any real outage.
- Every error message you saw, with a screenshot.

## Known limits (not bugs)
- Phones do not share orders with each other while offline. The kitchen only gets orders after reconnect, so the printed KOT is the kitchen's copy during the outage.
- Payments recorded in the system, final GST bills and reports need internet.
- A phone must have opened Native POS online at least once so the menu is saved.

---

# Test plan: 1 PC + 2 phones on the same Wi-Fi

PC = runs the app, plus Cashier (Chrome) and Kitchen (a different browser) logins. Use separate browsers, not two windows of one browser, because windows share one session and offline queue. Test offline on the phones only; switching off the PC's Wi-Fi also cuts the tunnel. Phone 1 = Waiter 1. Phone 2 = Waiter 2.

## Step 0. Why the phones cannot just open the PC address
- The app only listens on the PC itself (`127.0.0.1`), so phones cannot reach it.
- Phones also need **HTTPS**. Over plain `http://192.168.1.31:8180` the phone browser blocks the offline features (saved menu, offline queue) and may fail to send orders.
- So use a temporary HTTPS link. The PC already has `cloudflared` installed.

## Step 1. Prepare on the PC
1. [ ] Make sure the app is running: open `http://localhost:8180` and log in as Owner.
2. [ ] **Change the test passwords first** (Staff & access). The HTTPS link is public while it runs, so a weak password is a risk.
3. [ ] Owner: **Staff & access** → add a second waiter, `waiter2@pilot.local`, so each phone has its own login.
4. [ ] Owner: check that tables (at least 6) and some menu items with prices exist.
5. [ ] Open a terminal and run: `cloudflared tunnel --url http://localhost:8180`
6. [ ] Copy the link it prints, like `https://something-random.trycloudflare.com`. Keep the terminal open for the whole test.
7. [ ] When the test is over, press `Ctrl+C` in that terminal. The link then stops working.

## Step 2. Log in on each device
| Device | Open | Login |
|---|---|---|
| PC browser 1 (Chrome) | `http://localhost:8180` | Cashier |
| PC browser 2 (Firefox/Edge, or Incognito if Chrome only) | `http://localhost:8180` | Kitchen |
| Phone 1 | the `https://...trycloudflare.com` link | Waiter 1 |
| Phone 2 | the same link | Waiter 2 (`waiter2@pilot.local`) |

1. [ ] On both phones, open **Native POS** while online and wait until the menu and tables show. This saves them for offline use.
2. [ ] On both phones, reload the page once so the offline files are saved.
3. [ ] On both phones, switch on **Auto-print KOT** in Native POS. For printing, choose "Save as PDF" in the print window, since you have no printer connected.
4. [ ] Optional: Add to Home screen on each phone.

## Step 3. Normal order (everything online)
1. [ ] Phone 1: pick table T01, add 2 items, **Send to kitchen**. A print window opens.
2. [ ] PC Kitchen: the order appears. Accept it, then mark it ready.
3. [ ] Phone 1: add 1 more item to T01 (Orders → Add items). It must become **KOT 2**.
4. [ ] Phone 1: mark the order served.
5. [ ] PC Cashier: open the bill for T01 and check the total by hand. Take a cash payment and print.

## Step 4. Both waiters at the same time (online)
1. [ ] Phone 1 picks T02 and Phone 2 picks T03. Both tap **Send to kitchen** at the same moment. Both orders must arrive in the PC Kitchen.
2. [ ] Both phones pick the **same free table T04** and tap Send together (count "3, 2, 1, go"). One must succeed and the other must say "Table is not available".
3. [ ] Both phones add items to the running table T02 at the same moment. The Kitchen must show **two new KOTs** with different numbers.

## Step 5. Internet cut on the phones
Turn off Wi-Fi **and** mobile data on the phone. The PC stays online, so the Kitchen on the PC is your "kitchen".
1. [ ] Phone 1 goes offline. The yellow banner says "You are offline. Orders are safe on this device".
2. [ ] Phone 1: take an order on T05 and send it. It says saved on this device. A print window opens. The PC Kitchen shows **nothing yet**. That is expected.
3. [ ] Phone 1: close the browser completely, reopen the app (still offline). The order must show as "Waiting for internet".
4. [ ] Phone 1: switch Wi-Fi back on. Within about 30 seconds the order moves to "Sent to kitchen". The PC Kitchen now shows it, with the remark "Taken offline at HH:MM".
5. [ ] Check the count: orders you took offline = orders in the Orders screen.

## Step 6. Two phones offline on the same table
1. [ ] Turn Wi-Fi and mobile data off on **both** phones.
2. [ ] Phone 1 takes an order on T06 with item A. Phone 2 takes an order on T06 with item B.
3. [ ] Turn both back on at the same moment.
4. [ ] Result to expect: **one bill for T06 with both items, in two KOTs**. Nothing lost and nothing doubled.

## Step 7. Simulated 5-minute outage
1. [ ] Turn off the Wi-Fi router, or both phones' Wi-Fi, for 5 minutes.
2. [ ] During that time each phone takes 2 orders on different free tables.
3. [ ] Turn everything back on. All 4 orders must arrive in the Kitchen.

## Step 8. Phone restart and logout
1. [ ] Phone 1 offline: take an order, then **switch the phone off and on**. Reopen the app, then reconnect. The order must still send.
2. [ ] Phone 2 offline: take an order, log out, log in again as Waiter 2, then reconnect. The order must still send.

## Step 9. Permissions
1. [ ] Phone 1 (Waiter): try to give a discount, cancel an item, void or refund. All must be blocked.
2. [ ] PC Kitchen: it must not be able to create an order or take a payment.
3. [ ] PC Cashier: can discount and cancel an item, but cannot void or refund.
4. [ ] Log in as Manager: void and refund work.

## Step 10. Finish
1. [ ] PC Cashier: bill and pay every open table.
2. [ ] Owner: check Sales summary matches the bills you made, then run Day close.
3. [ ] Press `Ctrl+C` in the terminal to stop the HTTPS link.
4. [ ] Send me: your notes, screenshots of any error, and the phone models and browsers you used.

## If something goes wrong
- **Phone shows a blank page or "can't connect":** the terminal was closed or the link changed. Run the tunnel again and use the new link on both phones.
- **Menu is empty when offline:** that phone never opened Native POS online. Go online, open Native POS, wait for the menu, and try again.
- **Order not arriving after reconnect:** wait one minute, then open Native POS and look for a red "not accepted" message. Take a screenshot and send it to me.
- **Link changes each time** you restart the tunnel, so share the new one with the phones.
