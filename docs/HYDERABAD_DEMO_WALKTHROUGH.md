# Hyderabad Restaurant Demo Walkthrough

Use this script when presenting to a restaurant owner.

## Demo setup included

The seeded demo now includes:

- Outlet: **Demo Hyderabad Banjara Hills** (`built_in`)
- 12 tables
- 30 Hyderabad-style menu items (biryani, starters, tiffins, beverages, desserts)
- Historical sample orders/payments for trend analytics
- Open staff tasks (cleaning / serving / cashier)
- Active festival calendar entry for recommendation context

## How to run

```bash
cd /home/natraj/restaurant-revenue-platform
docker compose up --build -d
```

Open:

- Web app: `http://localhost:8180`
- API docs: `http://localhost:8181/docs`

Login:

- Email: `admin@demo.local`
- Password: `change-me-before-sharing`

## Owner demo flow (10–15 min)

1. **Dashboard (business value first)**
   - Show table readiness, active staff tasks, and configured cameras.
   - Explain: “This is the live operations control panel for service speed.”

2. **Staff Tasks page**
   - Show cleaning + serving + billing tasks.
   - Explain: “Tasks are role-targeted, so cleaning staff gets cleaning tasks, cashier gets billing follow-ups.”

3. **Native POS page**
   - Create a sample order from Hyderabad menu.
   - Explain: “In Full Stack plan, billing/order workflow is directly in our POS.”

   - Explain: “If you keep your current POS, we still provide monitoring + intelligence.”

5. **Analytics page**
   - Show actual collections metrics and trend chart.
   - Explain: “Actual revenue is kept separate from estimated opportunities.”

6. **Recommendations endpoint (optional live API view)**
   - `GET /api/v1/outlets/{outlet_id}/analytics/recommendations`
   - Explain day/meal-window/festival-based menu suggestions and confidence.

## Service positioning to owner

One plan: **RestoIQ POS** (₹499/outlet/month or ₹5,999/outlet/year, first month free)
- Complete POS with GST billing and KOT
- Table monitoring, delay alerts, staff tasking, revenue analytics, recommendations
