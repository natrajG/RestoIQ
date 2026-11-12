# RestoIQ: full on-site test scenarios

Use with `docs/PILOT_LOGINS.md` (logins and the 1 PC + 2 phones setup). Start with `./start_app.sh`, finish with `./stop_app.sh`.

How to use:
- Mark each row **P** (pass), **F** (fail) or **N/A** (the screen or feature does not exist or does not apply). Write the ID (for example `OFF-07`) next to every failure with a screenshot and the time.
- Rows marked **(!)** are the highest risk. Test these first if time is short.
- I wrote these from the app's menus and code. If a button has a different name on your screen, use the closest one and tell me.

Devices: **PC-A** Chrome = Cashier, **PC-B** Firefox/Edge = Kitchen, **Ph1** = Waiter 1, **Ph2** = Waiter 2. Log in as Owner or Manager on PC-A when a section says so.

Sections: 1 Access · 2 Setup · 3 Dine-in · 4 Kitchen · 5 Multi-waiter · 6 Offline · 7 Power cut · 8 Bill and payment · 9 Table actions · 10 Takeaway and delivery · 11 Permissions · 12 Customers · 13 Reports and day close · 14 Staff and tasks, 14b Camera and cleaning alerts · 15 Subscription and security · 16 Printing · 17 Devices and network · 18 Speed and stress · 19 Final reconciliation

---

## 1. Access and login
| ID | Do this | Expected | Result |
|---|---|---|---|
| AC-01 | Log in on each device with the correct role | Each role sees only its own menu items | |
| AC-02 | Log in with a wrong password 3 times | Clear error, no crash | |
| AC-03 | Use "forgot password" for one user | Reset mail or flow works, or shows a clear message | |
| AC-04 | Log out and press the browser Back button | You do not see the logged-in screens | |
| AC-05 | Open the link on a phone in portrait and landscape | Screens fit, buttons can be tapped | |
| AC-06 | Leave a phone idle for 30 minutes, then use it | Still logged in, or a clear login prompt (no blank page) | |
| AC-07 | Log in the same user on two devices | Note what happens (both work or one is signed out) | |
| AC-08 | Open the app and look at the sidebar for Waiter, Kitchen, Cleaner | Waiter: POS, floor, orders, kitchen, customers. Kitchen: kitchen, tasks. Cleaner: floor, tasks | |

## 2. Setup (Owner or Manager)
| ID | Do this | Expected | Result |
|---|---|---|---|
| SU-01 | Setup guide: follow every step | Steps tick off, no dead links | |
| SU-02 | Settings: restaurant name, address, GSTIN, phone, bill footer | Saved, and shown on the printed bill | |
| SU-03 | Tables & floor: add tables, sections and capacity | Tables appear on Live floor and Native POS | |
| SU-04 | Edit a table name, then delete an unused table | Works. A table with an open order cannot be deleted | |
| SU-05 | Menu: add a category and 5 items with price, GST % and veg/non-veg | Saved and shown in Native POS | |
| SU-06 | Menu: import items from a file, if you have one | Items appear with the right prices. Bad rows are reported | |
| SU-07 | Menu: switch an item off (sold out) | Waiters cannot add it | |
| SU-08 | Menu: change a price | New orders use the new price. Old bills are unchanged | |
| SU-09 | Menu: add item variants or add-ons if available | They show in Native POS and price correctly | |
| SU-10 | Settings: service charge, tax mode (inclusive or exclusive), round-off, UPI ID | The bill follows these settings | |
| SU-11 | Settings: Auto-print KOT on and off | KOT prints or not accordingly | |
| SU-12 | Staff & access: create waiter, cashier, kitchen, cleaner users | They can log in with the right role | |
| SU-13 | Staff & access: switch a user off | That user can no longer log in | |
| SU-14 | Staff & access: change a user's password | The old password stops working | |
| SU-15 | If you have 2 outlets: switch outlet in the top selector | Data (tables, orders) changes with the outlet | |

## 3. Dine-in order flow (online)
| ID | Do this | Expected | Result |
|---|---|---|---|
| DI-01 | **(!)** Ph1: pick a free table, add 2 items, Send to kitchen | KOT 1 prints. Table turns occupied on Live floor | |
| DI-02 | Add a note to an item (for example "less spicy") | Note shows on KOT and on the Kitchen screen | |
| DI-03 | Add an item with quantity 3 | KOT and bill show quantity 3 | |
| DI-04 | Remove an item before sending | It is not on the KOT | |
| DI-05 | **(!)** Add more items to the running table | **KOT 2** on the same bill. KOT 1 is unchanged | |
| DI-06 | Add items a third time | KOT 3, bill total is the sum of all | |
| DI-07 | Set the number of guests, if asked | Saved with the order | |
| DI-08 | Search the menu by name and by category | Finds the item fast | |
| DI-09 | Try to send an empty order | Blocked with a message | |
| DI-10 | Cancel one sent item (as a role that may) | Item is struck out. A cancel slip can be printed. Bill reduces | |
| DI-11 | Mark the order served | Status changes. The Kitchen screen clears it | |
| DI-12 | Open the Orders screen | Every order shows the right table, items, KOT numbers and status | |
| DI-13 | Take 10 orders and check the KOT numbers | Sequential, no gaps, no duplicates | |

## 4. Kitchen screen (PC-B)
| ID | Do this | Expected | Result |
|---|---|---|---|
| KT-01 | A new order from a phone | Appears on Kitchen in a few seconds, with table, items, notes | |
| KT-02 | Accept the order | Status changes. The waiter sees it | |
| KT-03 | Mark it ready | The waiter sees "ready" | |
| KT-04 | Add items to a running order | The new KOT shows as a separate ticket or clearly marked | |
| KT-05 | A cancelled item | Kitchen sees it cancelled | |
| KT-06 | Offline-taken order arrives after reconnect | Shows the remark "Taken offline at HH:MM". Write down if the Kitchen screen does not show it | |
| KT-07 | Refresh the Kitchen browser | Open orders are still listed | |
| KT-08 | Leave the Kitchen screen open for 1 hour | It keeps updating without a manual refresh | |
| KT-09 | Is there a sound or alert for a new order? | Note: yes or no, and whether the cook notices | |
| KT-10 | **(!)** Kitchen taps "Food ready" while the waiter is on Native POS or Orders | Within about 5 seconds the waiter sees a popup: "Pick up order 123 and serve table T04" | |
| KT-11 | Waiter misses the popup (popup lasts about 8 seconds) | Task is still listed in Staff tasks. Note how often waiters miss it in a busy period | |
| KT-12 | Kitchen screen card titles | Dine-in shows the table name (for example "T04 · 123"). Takeaway or delivery shows its type. A ready order shows "READY: take to T04" | |

## 5. Several waiters at the same time (online)
| ID | Do this | Expected | Result |
|---|---|---|---|
| MW-01 | **(!)** Ph1 on T02 and Ph2 on T03 tap Send together | Both arrive. No errors | |
| MW-02 | **(!)** Both phones pick the same free table and tap Send together ("3, 2, 1, go") | One wins. The other sees "Table is not available" and nothing is lost | |
| MW-03 | **(!)** Both phones add items to the same running table together | Two new KOTs with different numbers. Both item sets are on the bill | |
| MW-04 | Ph1 adds items while PC-A is opening the bill | No error. The bill total includes the new items after refresh | |
| MW-05 | Ph1 cancels an item while Ph2 adds an item, same table | Both actions apply. The bill is right | |
| MW-06 | Three waiters (use Ph1, Ph2 and a PC login) order on 3 tables within 10 seconds | All arrive, KOT numbers distinct | |
| MW-07 | Count: orders made versus orders in the system | Equal. None missing, none doubled | |
| MW-08 | Double-tap the Send button quickly on one phone | Only one order is created | |

## 6. Internet cut: offline mode (**the most important section**)
Switch off Wi-Fi **and** mobile data on the phone (not on the PC).
| ID | Do this | Expected | Result |
|---|---|---|---|
| OFF-01 | Turn the phone offline | Yellow banner: "You are offline. Orders are safe on this device" | |
| OFF-02 | **(!)** Take a new order on a free table | "Saved on this device". A KOT prints (Save as PDF) | |
| OFF-03 | **(!)** Close the browser fully, reopen it offline | The order is listed as "Waiting for internet". Menu and tables still load | |
| OFF-04 | **(!)** Refresh the page while offline | The order is still there | |
| OFF-05 | Switch the phone off and on, then reopen offline | The order is still there | |
| OFF-06 | **(!)** Reconnect | Within about 30 seconds the order shows "Sent to kitchen". PC-B Kitchen shows it | |
| OFF-07 | **(!)** Offline: add items to a table that is already running | New KOT prints. After reconnect it joins the same bill | |
| OFF-08 | **(!)** Both phones offline, same free table, one order each, then reconnect both at the same moment | One bill, two KOTs, nothing lost or doubled | |
| OFF-09 | Both phones offline, different tables, reconnect together | All orders arrive once | |
| OFF-10 | Take 5 orders offline on one phone, then reconnect | All 5 arrive once, in order | |
| OFF-11 | Reconnect while the app is closed. Open the app later | The queue sends on opening | |
| OFF-12 | Log out while orders are waiting, then log in again | The orders are still there and send | |
| OFF-13 | Log in as a different waiter on the same phone, offline orders waiting | Note what happens. Orders must not be lost or sent under the wrong restaurant | |
| OFF-14 | **(!)** Flip the connection on and off 5 times while an order is waiting | The order arrives exactly once | |
| OFF-15 | Very weak signal (move to a far corner) | No duplicate orders. A clear status | |
| OFF-16 | Open the app for the first time while offline (never opened online) | Note what happens. Expected: it cannot load. This is a known limit | |
| OFF-17 | Offline order on a table taken online by someone else meanwhile | Items join the running order, or you get a clear message. Nothing is lost | |
| OFF-18 | Offline payment recorded, then reconnect | Payment is recorded once | |
| OFF-19 | Check the offline order's KOT number after sync | Numbers are in order and do not clash with other waiters | |
| OFF-20 | Count after every offline test: orders taken versus orders in the system | Equal | |

## 7. Power cut and generator (about 5 minutes)
| ID | Do this | Expected | Result |
|---|---|---|---|
| PW-01 | **(!)** Switch off the router for 5 minutes. Take 4 orders on the phones | All saved on the phones | |
| PW-02 | Switch the router back on | All 4 orders arrive once | |
| PW-03 | Real or simulated outage: PC loses power and restarts | After restart run `./start_app.sh`. No data is lost | |
| PW-04 | Printer power cut and restart | It prints again. Note whether a KOT was lost | |
| PW-05 | Phone battery at 10% with unsent orders | The orders are still there after charging and reopening | |
| PW-06 | How long does the router and PC take to be ready after power returns? | Write down the minutes | |
| PW-07 | Does the app (`docker`) start by itself after the PC reboots? | Note: yes or no | |

## 8. Bill and payment (PC-A Cashier)
| ID | Do this | Expected | Result |
|---|---|---|---|
| BP-01 | Open a bill and calculate the total by hand | Subtotal, GST, service charge and round-off match your calculation | |
| BP-02 | Check 3 different bills with items at different GST rates | Tax per item is right. Total matches | |
| BP-03 | Apply a % discount | Total reduces and tax is right | |
| BP-04 | Apply a fixed ₹ discount | Same | |
| BP-05 | Discount more than the bill | Blocked or capped | |
| BP-06 | Add a tip | Tip is not taxed and is added to the amount payable | |
| BP-07 | Pay by cash and record the cash received | Change due is shown right | |
| BP-08 | Pay by card (machine used outside the app), record "Card" | Bill is closed with mode Card | |
| BP-09 | Pay by UPI, record "UPI". Check the UPI QR if shown | Bill is closed. The QR uses the right UPI ID and amount | |
| BP-10 | **(!)** Split payment: half cash, half UPI | Both parts add up to the total. The bill closes only at the full amount | |
| BP-11 | Pay less than the total | The bill stays open with the balance shown | |
| BP-12 | Pay more than the total in cash | Blocked, or change is shown | |
| BP-13 | Pay the same bill twice (tap Pay twice quickly) | Only one payment is saved | |
| BP-14 | Print the bill | Restaurant name, GSTIN, bill number, date, items, tax, total and footer are right | |
| BP-15 | Reprint a closed bill | Marked as a duplicate or the same content | |
| BP-16 | Bill numbers across 10 bills | Sequential, no gaps, no duplicates | |
| BP-17 | Try to edit a paid bill | Blocked | |
| BP-18 | Paid table goes to cleaning | Table shows cleaning. The cleaner marks it clean. It is free again | |
| BP-19 | Waiter marks a payment (payment mode only) | Works, and the Exceptions or order log shows who recorded it | |
| BP-20 | Split the bill equally among N people | Each share adds up to the total | |
| BP-21 | Check a bill with a customer GSTIN, if the field exists | GSTIN prints on the bill | |

## 9. Table actions
| ID | Do this | Expected | Result |
|---|---|---|---|
| TA-01 | Shift a running order to another free table | The old table is free. The new one is occupied. Items and KOTs are kept | |
| TA-02 | Shift to an occupied table | Blocked | |
| TA-03 | Merge two running tables into one bill | One bill with all items. The other table is free | |
| TA-04 | Split a bill into two bills | Two bills, totals add up to the original | |
| TA-05 | Merge, then try to pay the old order | Blocked, or it no longer exists | |
| TA-06 | Void an open order with a reason | Requires a reason. Table is freed. It is in Exceptions | |
| TA-07 | Live floor: table colours | Free, occupied, bill requested and cleaning colours are right | |
| TA-08 | Two people shift the same order at the same time | One wins, with no corruption | |
| TA-09 | Reserve a table, if available | It shows as reserved and cannot be taken | |

## 10. Takeaway and delivery
| ID | Do this | Expected | Result |
|---|---|---|---|
| TD-01 | Create a takeaway order with a customer name and phone | KOT prints. The bill has no table | |
| TD-02 | Pay a takeaway order | Closes correctly | |
| TD-03 | Create a delivery order with an address | Shows on the Delivery screen | |
| TD-04 | Move a delivery through its statuses | Status changes are saved | |
| TD-05 | Takeaway order taken offline | Saved, sent after reconnect, no table needed | |
| TD-06 | Packing charge or delivery charge, if available | Applied and taxed as set | |

## 11. Permissions (these must be blocked)
| ID | Role | Try | Expected | Result |
|---|---|---|---|---|
| PM-01 | Waiter | Give a discount | Blocked | |
| PM-02 | Waiter | Cancel a sent item | Blocked | |
| PM-03 | Waiter | Void or refund | Blocked | |
| PM-04 | Waiter | Open Menu, Staff, Settings, Reports, Subscription | Not in the menu. A direct link shows "no access" | |
| PM-05 | Kitchen | Create an order, add items or take a payment | Blocked | |
| PM-06 | Cleaner | Create an order or take a payment | Blocked | |
| PM-07 | Cashier | Discount and cancel an item | Allowed | |
| PM-08 | Cashier | Void or refund | Blocked | |
| PM-09 | Manager | Void and refund with a reason | Allowed. Shows in Exceptions | |
| PM-10 | Manager | Staff and settings | Allowed. Subscription is not allowed | |
| PM-11 | Owner | Everything, including Subscription and reports | Allowed | |
| PM-12 | Any role | Type another page's address directly in the browser | Blocked or redirected | |
| PM-13 | Switched-off user | Try to log in | Blocked | |
| PM-14 | Exceptions screen | Does every void, refund, discount and cancel show who did it and when? | Yes | |

## 12. Customers
| ID | Do this | Expected | Result |
|---|---|---|---|
| CU-01 | Add a customer with a name and phone | Saved | |
| CU-02 | Attach the customer to an order | Shown on the bill | |
| CU-03 | Search the customer by phone | Found | |
| CU-04 | Add the same phone twice | No duplicate, or a clear message | |
| CU-05 | Loyalty, coupons or credit, if present | Calculated correctly. Mark N/A if not present | |

## 13. Reports and day close
| ID | Do this | Expected | Result |
|---|---|---|---|
| RP-01 | Sales summary after your test bills | Total equals the sum of the bills. Split by payment mode (cash, card, UPI) matches | |
| RP-02 | Check one voided bill | Not counted in sales. Listed in Exceptions | |
| RP-03 | GST report | Tax amounts match the bills, by rate | |
| RP-04 | Reports and Analytics: pick today | Top items, hours and totals look right | |
| RP-05 | Overview dashboard | Live numbers match reality (open tables, sales) | |
| RP-06 | **(!)** Day close: count the cash in the drawer | Expected cash equals counted cash, or the difference is shown | |
| RP-07 | Day close: enter a cash difference | Saved with a note | |
| RP-08 | After Day close, take a new order | Behaves as the next day or session, as you expect | |
| RP-09 | Export a report, if there is a button | File opens and the numbers match | |
| RP-10 | Change the date range | Numbers change correctly | |

## 14. Staff and tasks
| ID | Do this | Expected | Result |
|---|---|---|---|
| ST-01 | Cleaner: Live floor shows tables needing cleaning | Marks clean, and the table is free | |
| ST-02 | Staff tasks: create a task and assign it | The assignee sees it and can complete it | |
| ST-03 | Customer requests (call waiter, bill request), if present | Appear for staff | |
| ST-04 | AI monitoring (cameras): open the screen | Opens without errors. Mark N/A if no camera is connected | |

## 14b. Camera monitoring and cleaning alerts
Needs an IP camera with an RTSP address on the same network as the PC. The vision service runs on the PC. Only people are detected, one picture per second.
| ID | Do this | Expected | Result |
|---|---|---|---|
| CM-01 | Find the camera's RTSP address (from the camera app or box, like `rtsp://user:pass@192.168.1.10:554/stream1`) and test it first in VLC on the PC | Video plays. If VLC fails, the app will fail too | |
| CM-02 | Owner or Manager: AI monitoring → add camera, source "Live RTSP stream", paste the address | Saved. The address is hidden afterwards | |
| CM-03 | Enter a bad address, `localhost`, or a wrong port | Rejected with a clear message | |
| CM-04 | Upload a reference picture of the floor and draw each table's area (region) on it | Each table maps to its area on the picture | |
| CM-05 | Check "Not covered by any camera" | Lists any table with no area. Every table you want watched is covered | |
| CM-06 | Camera status on the screen | Shows online and the last time it was seen | |
| CM-07 | **(!)** A guest sits at an empty, watched table | Within a few seconds the table turns occupied and the waiter gets a popup: "Guests seated at T04: greet and take the order" | |
| CM-08 | **(!)** The guest leaves | The table turns dirty and the **cleaner** gets a popup: "Guests left T04: clean and reset the table" | |
| CM-09 | Cleaner opens Staff tasks, acknowledges, then completes the task | Table becomes free. The task disappears | |
| CM-10 | Walk past or stand next to a table without sitting | No false task | |
| CM-11 | A waiter standing at an empty table for 1 minute | Note whether it wrongly counts as guests | |
| CM-12 | A guest briefly stands up and returns | No cleaning task | |
| CM-13 | **(!)** Guests leave plates, glasses or bowls on the table | The cleaner's popup says "Guests left T04: clear the dishes and reset the table". Dishes are only detected if the camera can see them | |
| CM-13b | Guests leave and the table is completely bare | The popup says "clean and reset the table" (no dishes mentioned) | |
| CM-13c | Which things are detected as dishes? Try a plate, a thali, steel bowls, glasses, cups, bottles, and a food item | Write which ones are detected and which are missed. Flat plates and thalis are the most likely to be missed | |
| CM-14 | Table is occupied from an order, then the guest leaves | Check which one changes the table first (POS or camera) and note any conflict | |
| CM-15 | Cleaner on a phone with the app open on the Floor screen | Popup appears. Remember it shows for about 8 seconds and is hidden if the cleaner has Staff tasks open | |
| CM-16 | Cleaner phone offline | No popup. Note this | |
| CM-17 | Manager assigns a cleaning task to a specific person | That person sees it | |
| CM-18 | Restaurant lighting at night, backlight or a crowd | Note how often the table state is wrong. Give me examples | |
| CM-19 | Unplug the camera or the network cable | Status shows no signal. No false tasks are created | |
| CM-20 | Restart the PC and run `./start_app.sh` | The camera comes back online by itself. The first sighting does not create a "guests seated" task | |
| CM-21 | Count 10 real seatings and 10 real departures | Tasks created match the real events. Write the number of misses and false alarms | |
| CM-22 | Privacy: is the camera pointed at tables and not at the cash counter, kitchen or guests' faces? A sign about camera use is displayed | Yes. Legal and staff notice are your responsibility | |

## 15. Subscription and security
| ID | Do this | Expected | Result |
|---|---|---|---|
| SB-01 | Owner: Subscription screen | Shows the trial end date and the plan (₹499/month, ₹5,999/year) | |
| SB-02 | Start a payment in test mode, if configured | Works, or shows a clear message. I have not tested this end to end | |
| SB-03 | Change every test password | Old passwords stop working | |
| SB-04 | **(!)** Open the tunnel link from a phone on mobile data (not Wi-Fi) | Loads. Login is required | |
| SB-05 | Open the tunnel link without logging in and try `/orders` | Redirects to login | |
| SB-06 | Log in to a second restaurant account, if you have one | You never see the other restaurant's orders or menu | |
| SB-07 | After the test, run `./stop_app.sh` and open the link | The link no longer works | |

## 16. Printing
| ID | Do this | Expected | Result |
|---|---|---|---|
| PR-01 | Print a KOT to the real printer | Readable, table, KOT number, time, items and notes shown | |
| PR-02 | Paper width 58 mm and 80 mm | Text is not cut off | |
| PR-03 | Print from the phone and from the PC | Both work. Note how (Bluetooth, network or PDF) | |
| PR-04 | **(!)** Print a KOT while offline | Prints from the phone without internet (if the printer is local) | |
| PR-05 | After reconnecting, check that the KOT is **not printed twice** | One print per KOT | |
| PR-06 | Print a cancel slip | Shows the cancelled item and the table | |
| PR-07 | Reprint a KOT | Allowed, and marked as a reprint if the app says so | |
| PR-08 | Out of paper or printer off | A clear failure. The order is not lost | |
| PR-09 | Kitchen and bar on separate printers, if needed | Note whether the app supports it. Mark N/A if not needed | |

## 17. Devices and network
| ID | Do this | Expected | Result |
|---|---|---|---|
| DN-01 | Android Chrome and iPhone Safari | Everything above works on both | |
| DN-02 | Add to Home screen and open from the icon | Opens full screen and works offline | |
| DN-03 | Switch from Wi-Fi to mobile data in the middle of an order | The order is sent once | |
| DN-04 | Walk across the restaurant on Wi-Fi | Orders keep working. Note dead spots | |
| DN-05 | A cheap or old phone | Not slow or frozen | |
| DN-06 | Restaurant Wi-Fi blocks the tunnel (no link appears) | Use the PC on a mobile hotspot. Note what happened | |
| DN-07 | Rotate the phone, zoom, large font setting | Buttons are still usable | |
| DN-08 | Phone language or date format is different | Dates and amounts look right | |

## 18. Speed and stress
| ID | Do this | Expected | Result |
|---|---|---|---|
| SP-01 | Time from tapping Send to the KOT printing | Under 3 seconds. Write the number | |
| SP-02 | Time from Send to the order showing on Kitchen | Under 5 seconds | |
| SP-03 | **(!)** A busy 15 minutes: every waiter orders constantly | No errors, no freezing, no duplicates | |
| SP-04 | 30 open orders at once | Screens stay fast | |
| SP-05 | Leave the app open for 3 hours | Still works with no restart | |
| SP-06 | Ask each waiter: what was confusing or slow? | Write down every answer | |
| SP-07 | Train a new waiter for 5 minutes, then watch | Note where they get stuck | |

## 19. Final reconciliation (end of the test)
1. [ ] Count every order you took on paper or a list. Compare with the Orders screen. Number missing: ___ Number doubled: ___
2. [ ] Count every KOT printed. Compare with the KOT numbers in the system. Gaps or duplicates: ___
3. [ ] Add up all bills by hand. Compare with Sales summary. Difference: ___
4. [ ] Compare cash, card and UPI totals with the Day close screen. Difference: ___
5. [ ] Every void, refund and discount appears in Exceptions.
6. [ ] No table is left stuck as occupied.
7. [ ] Run `./stop_app.sh`.

## What to send me
- This file with the Result column filled in, and a screenshot for every **F**.
- Phone models, browsers and the Wi-Fi quality per area.
- Printer model and how it is connected.
- The longest internet outage you saw and how long the generator took.
- A list of anything you wanted the app to do that it did not.

## Go or no-go
- **Must pass before real use:** every **(!)** row, all of sections 6, 7 and 11, BP-01 to BP-16, RP-01 to RP-06 and KT-10.
- If any order is lost or doubled, or a bill total is wrong, it is a no-go. Send me the details first.
