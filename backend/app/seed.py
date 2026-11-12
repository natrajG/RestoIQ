from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select

from app.core.config import settings
from app.core.subscriptions import DEFAULT_PLAN, set_tenant_plan
from app.auth.service import hash_password
from app.db import SessionLocal, set_tenant_context
from app.models import (
    Customer,
    DiningTable,
    Employee,
    Floor,
    FestivalCalendar,
    InventoryItem,
    MenuCategory,
    MenuItem,
    OrderItem,
    OutletMembership,
    Payment,
    Restaurant,
    RestaurantOrder,
    StaffTask,
    Tenant,
    User,
    now_utc,
)


def seed_platform_admin() -> None:
    if not (settings.platform_admin_email and settings.platform_admin_password):
        return
    with SessionLocal() as db:
        tenant = db.scalar(select(Tenant).where(Tenant.name == "Demo Hospitality")) or db.scalar(select(Tenant).order_by(Tenant.id))
        if not tenant:
            tenant = Tenant(name="Demo Hospitality")
            db.add(tenant)
            db.flush()
        set_tenant_context(db, tenant.id)
        email = settings.platform_admin_email.lower()
        if not db.scalar(select(User).where(User.email == email)):
            db.add(User(tenant_id=tenant.id, email=email, role="platform_admin",
                        password_hash=hash_password(settings.platform_admin_password)))
        db.commit()


def seed_demo() -> None:
    if not settings.seed_demo or settings.environment.strip().lower() != "development":
        return
    build_demo("Demo Hospitality", settings.demo_admin_email, settings.demo_admin_password, "demo.local")


def build_demo(tenant_name: str, owner_email: str, password: str, staff_domain: str, volume: int = 1) -> None:
    with SessionLocal() as db:
        tenant = db.scalar(select(Tenant).where(Tenant.name == tenant_name))
        if not tenant:
            tenant = Tenant(name=tenant_name)
            db.add(tenant)
            db.flush()
        set_tenant_context(db, tenant.id)
        set_tenant_plan(db, tenant.id, DEFAULT_PLAN)
        user = db.scalar(select(User).where(User.email == owner_email.lower()))
        if not user:
            user = User(
                tenant_id=tenant.id, email=owner_email.lower(),
                password_hash=hash_password(password), role="owner",
            )
            db.add(user)
        restaurant = db.scalar(select(Restaurant).where(
            Restaurant.tenant_id == tenant.id, Restaurant.name == "Demo Hyderabad Banjara Hills",
        ))
        legacy_native = db.scalar(select(Restaurant).where(
            Restaurant.tenant_id == tenant.id, Restaurant.name == "Demo Bengaluru",
        ))
        if not restaurant and legacy_native:
            legacy_native.name = "Demo Hyderabad Banjara Hills"
            legacy_native.state_code = "TS"
            restaurant = legacy_native
        if not restaurant:
            restaurant = Restaurant(
                tenant_id=tenant.id, name="Demo Hyderabad Banjara Hills", timezone="Asia/Kolkata",
                currency="INR", state_code="TS",
                tax_config={"currency": "INR", "tax_mode": "configurable", "accountant_review_required": True},
            )
            db.add(restaurant)
            db.flush()

        floor = db.scalar(select(Floor).where(Floor.restaurant_id == restaurant.id, Floor.name == "Main Floor"))
        if not floor:
            floor = Floor(tenant_id=tenant.id, restaurant_id=restaurant.id, name="Main Floor")
            db.add(floor)
            db.flush()

        tables = db.scalars(select(DiningTable).where(
            DiningTable.tenant_id == tenant.id, DiningTable.restaurant_id == restaurant.id,
        )).all()
        existing_names = {table.name for table in tables}
        for index in range(1, 13):
            name = f"T{index:02}"
            if name not in existing_names:
                db.add(DiningTable(
                    tenant_id=tenant.id, restaurant_id=restaurant.id, name=name,
                    floor_id=floor.id,
                    seats=2 if index <= 6 else 4, x=float((index - 1) % 4), y=float((index - 1) // 4),
                    status="OCCUPIED" if index == 2 else "DIRTY" if index == 9 else "FREE",
                ))

        category_names = [
            "Hyderabadi Starters",
            "Biryani Specials",
            "Main Course",
            "Breads",
            "Breakfast Tiffins",
            "Beverages",
            "Desserts",
        ]
        categories_by_name: dict[str, MenuCategory] = {}
        for order, category_name in enumerate(category_names):
            category = db.scalar(select(MenuCategory).where(
                MenuCategory.tenant_id == tenant.id,
                MenuCategory.restaurant_id == restaurant.id,
                MenuCategory.name == category_name,
            ))
            if not category:
                category = MenuCategory(
                    tenant_id=tenant.id,
                    restaurant_id=restaurant.id,
                    name=category_name,
                    sort_order=order,
                )
                db.add(category)
                db.flush()
            categories_by_name[category_name] = category

        sample_items = [
            ("Hyderabadi Chicken 65", "HYD-ST-001", 320, "Hyderabadi Starters"),
            ("Apollo Fish", "HYD-ST-002", 360, "Hyderabadi Starters"),
            ("Mutton Ghee Roast", "HYD-ST-003", 420, "Hyderabadi Starters"),
            ("Paneer 65", "HYD-ST-004", 280, "Hyderabadi Starters"),
            ("Mirchi Bajji", "HYD-ST-005", 150, "Hyderabadi Starters"),
            ("Hyderabadi Dum Chicken Biryani", "HYD-BR-001", 360, "Biryani Specials"),
            ("Hyderabadi Dum Mutton Biryani", "HYD-BR-002", 440, "Biryani Specials"),
            ("Paneer Biryani", "HYD-BR-003", 320, "Biryani Specials"),
            ("Egg Biryani", "HYD-BR-004", 260, "Biryani Specials"),
            ("Prawns Biryani", "HYD-BR-005", 460, "Biryani Specials"),
            ("Bagara Rice with Dalcha", "HYD-MC-001", 290, "Main Course"),
            ("Chicken Haleem Bowl", "HYD-MC-002", 280, "Main Course"),
            ("Mutton Marag", "HYD-MC-003", 320, "Main Course"),
            ("Kodi Kura", "HYD-MC-004", 340, "Main Course"),
            ("Vegetable Kurma", "HYD-MC-005", 220, "Main Course"),
            ("Rumali Roti", "HYD-BD-001", 40, "Breads"),
            ("Tandoori Roti", "HYD-BD-002", 35, "Breads"),
            ("Butter Naan", "HYD-BD-003", 65, "Breads"),
            ("Laccha Paratha", "HYD-BD-004", 80, "Breads"),
            ("Khubani Naan", "HYD-BD-005", 95, "Breads"),
            ("Idli Sambar", "HYD-BF-001", 120, "Breakfast Tiffins"),
            ("Ghee Karam Dosa", "HYD-BF-002", 180, "Breakfast Tiffins"),
            ("Pesarattu Upma", "HYD-BF-003", 170, "Breakfast Tiffins"),
            ("Poori Aloo Curry", "HYD-BF-004", 160, "Breakfast Tiffins"),
            ("Irani Chai", "HYD-BV-001", 60, "Beverages"),
            ("Qubani Mocktail", "HYD-BV-002", 140, "Beverages"),
            ("Badam Milk", "HYD-BV-003", 110, "Beverages"),
            ("Double Ka Meetha", "HYD-DS-001", 130, "Desserts"),
            ("Qubani Ka Meetha", "HYD-DS-002", 150, "Desserts"),
            ("Apricot Kulfi", "HYD-DS-003", 120, "Desserts"),
        ]
        for name, sku, raw_price, category_name in sample_items:
            if not db.scalar(select(MenuItem.id).where(MenuItem.restaurant_id == restaurant.id, MenuItem.sku == sku)):
                price = Decimal(raw_price)
                db.add(MenuItem(
                    tenant_id=tenant.id,
                    restaurant_id=restaurant.id,
                    category_id=categories_by_name[category_name].id,
                    name=name,
                    sku=sku,
                    price=price,
                    cost_price=price * Decimal("0.4"),
                    tax_rate=Decimal("5"),
                ))

        stock = [
            ("ING-001", "Sella basmati rice", "kg", Decimal("18"), Decimal("6"), Decimal("140")),
            ("ING-002", "Chicken (cleaned)", "kg", Decimal("22"), Decimal("8"), Decimal("260")),
            ("ING-003", "Mutton", "kg", Decimal("12"), Decimal("4"), Decimal("720")),
            ("ING-004", "Apricot pulp", "kg", Decimal("6"), Decimal("2"), Decimal("300")),
            ("ING-005", "Irani tea blend", "kg", Decimal("4"), Decimal("1"), Decimal("780")),
        ]
        for sku, name, unit, quantity, reorder, cost in stock:
            if not db.scalar(select(InventoryItem.id).where(InventoryItem.restaurant_id == restaurant.id, InventoryItem.sku == sku)):
                db.add(InventoryItem(
                    tenant_id=tenant.id, restaurant_id=restaurant.id, sku=sku, name=name, unit=unit,
                    quantity_on_hand=quantity, reorder_level=reorder, unit_cost=cost,
                ))
        demo_staff = [
            (f"cleaner@{staff_domain}", "Cleaning Staff", "cleaning", Decimal("18000")),
            (f"server@{staff_domain}", "Serving Staff", "waiter", Decimal("22000")),
            (f"kitchen@{staff_domain}", "Kitchen Staff", "kitchen", Decimal("25000")),
            (f"cashier@{staff_domain}", "Cashier", "cashier", Decimal("24000")),
        ]
        for email, display_name, role, salary in demo_staff:
            member = db.scalar(select(User).where(User.email == email))
            if not member:
                member = User(
                    tenant_id=tenant.id, email=email,
                    password_hash=hash_password(password), role=role,
                )
                db.add(member)
                db.flush()
            if not db.scalar(select(OutletMembership.id).where(
                OutletMembership.outlet_id == restaurant.id,
                OutletMembership.user_id == member.id,
            )):
                db.add(OutletMembership(
                    tenant_id=tenant.id, outlet_id=restaurant.id, user_id=member.id, role=role,
                ))
            if not db.scalar(select(Employee.id).where(
                Employee.tenant_id == tenant.id, Employee.restaurant_id == restaurant.id,
                Employee.email == email,
            )):
                db.add(Employee(
                    tenant_id=tenant.id, restaurant_id=restaurant.id, display_name=display_name,
                    role=role, email=email, monthly_salary=salary,
                ))
        if not db.scalar(select(Customer.id).where(
            Customer.tenant_id == tenant.id, Customer.restaurant_id == restaurant.id,
        )):
            for cname, cphone, pts in [
                ("Ravi Teja", "+919876543210", 120), ("Sneha Reddy", "+919876543211", 340),
                ("Arjun Rao", "+919876543212", 60), ("Lakshmi Devi", "+919876543213", 210),
                ("Imran Khan", "+919876543214", 480),
            ]:
                db.add(Customer(
                    tenant_id=tenant.id, restaurant_id=restaurant.id, name=cname,
                    phone=cphone, email=f"{cname.split()[0].lower()}@example.test", loyalty_points=pts,
                ))
        menu_items = db.scalars(select(MenuItem).where(
            MenuItem.tenant_id == tenant.id,
            MenuItem.restaurant_id == restaurant.id,
        )).all()
        menu_by_sku = {item.sku: item for item in menu_items}
        if not db.scalar(select(RestaurantOrder.id).where(
            RestaurantOrder.tenant_id == tenant.id,
            RestaurantOrder.restaurant_id == restaurant.id,
        )):
            table_ids = db.scalars(select(DiningTable.id).where(
                DiningTable.tenant_id == tenant.id,
                DiningTable.restaurant_id == restaurant.id,
            ).order_by(DiningTable.name)).all()
            demand_patterns = [
                (27, [("HYD-BF-001", 2), ("HYD-BV-001", 2)], "paid"),
                (26, [("HYD-BF-002", 2), ("HYD-BV-003", 1)], "paid"),
                (24, [("HYD-BR-001", 2), ("HYD-BV-002", 2)], "paid"),
                (23, [("HYD-BR-002", 1), ("HYD-ST-002", 1)], "paid"),
                (22, [("HYD-BR-001", 2), ("HYD-ST-001", 1)], "paid"),
                (21, [("HYD-BR-003", 2), ("HYD-DS-001", 2)], "paid"),
                (19, [("HYD-BF-003", 2), ("HYD-BV-001", 2)], "paid"),
                (18, [("HYD-BF-001", 2), ("HYD-BV-001", 2)], "paid"),
                (17, [("HYD-BR-001", 2), ("HYD-ST-001", 1)], "paid"),
                (16, [("HYD-BR-002", 1), ("HYD-ST-003", 1)], "paid"),
                (15, [("HYD-BR-004", 2), ("HYD-DS-002", 1)], "paid"),
                (14, [("HYD-BR-001", 2), ("HYD-ST-002", 1)], "paid"),
                (13, [("HYD-BF-001", 2), ("HYD-BV-001", 2)], "paid"),
                (12, [("HYD-BF-002", 2), ("HYD-BV-003", 1)], "paid"),
                (11, [("HYD-BR-001", 3), ("HYD-ST-001", 2)], "paid"),
                (10, [("HYD-BR-002", 2), ("HYD-ST-002", 1)], "paid"),
                (9, [("HYD-BR-003", 2), ("HYD-DS-003", 2)], "paid"),
                (8, [("HYD-BR-001", 3), ("HYD-BV-002", 2)], "paid"),
                (7, [("HYD-BF-001", 2), ("HYD-BV-001", 2)], "paid"),
                (6, [("HYD-BF-002", 2), ("HYD-BV-001", 2)], "paid"),
                (5, [("HYD-BR-001", 3), ("HYD-ST-001", 2)], "paid"),
                (4, [("HYD-BR-002", 2), ("HYD-ST-003", 1)], "paid"),
                (3, [("HYD-BR-001", 2), ("HYD-DS-002", 1)], "paid"),
                (2, [("HYD-BR-001", 2), ("HYD-BV-002", 2)], "paid"),
                (1, [("HYD-BR-001", 2), ("HYD-ST-001", 1)], "paid"),
                (0, [("HYD-BR-001", 2), ("HYD-ST-004", 1)], "submitted"),
            ]
            methods = ["upi_external", "cash", "card"]
            expanded = [(d, l, st, rep_no) for d, l, st in demand_patterns for rep_no in range(volume)]
            for index, (days_ago, lines, status, rep_no) in enumerate(expanded, start=1):
                created_at = now_utc() - timedelta(days=days_ago, hours=2 + rep_no * 3)
                if status != "paid" and rep_no:
                    continue
                subtotal = Decimal("0")
                tax_total = Decimal("0")
                order = RestaurantOrder(
                    tenant_id=tenant.id,
                    restaurant_id=restaurant.id,
                    table_id=table_ids[(index - 1) % len(table_ids)] if table_ids else None,
                    order_number=f"HYD-{created_at:%y%m%d}-{index:03d}",
                    order_type="dine_in",
                    status=status,
                    source="built_in",
                    subtotal=Decimal("0"),
                    tax_total=Decimal("0"),
                    discount_total=Decimal("0"),
                    total=Decimal("0"),
                    created_at=created_at,
                    updated_at=created_at,
                )
                db.add(order)
                db.flush()
                for sku, quantity in lines:
                    menu_item = menu_by_sku.get(sku)
                    if not menu_item:
                        continue
                    line_total = menu_item.price * quantity
                    subtotal += line_total
                    tax_total += (line_total * menu_item.tax_rate / Decimal("100"))
                    db.add(OrderItem(
                        tenant_id=tenant.id,
                        order_id=order.id,
                        menu_item_id=menu_item.id,
                        item_name=menu_item.name,
                        quantity=quantity,
                        unit_price=menu_item.price,
                        tax_rate=menu_item.tax_rate,
                        line_total=line_total,
                    ))
                order.subtotal = subtotal.quantize(Decimal("0.01"))
                order.tax_total = tax_total.quantize(Decimal("0.01"))
                order.total = (order.subtotal + order.tax_total).quantize(Decimal("0.01"))
                if status == "paid":
                    db.add(Payment(
                        tenant_id=tenant.id,
                        order_id=order.id,
                        method=methods[index % 3],
                        status="recorded",
                        amount=order.total,
                        reference=f"DEMO-{index:04d}",
                        idempotency_key=f"seed-payment-{index}",
                        created_at=created_at + timedelta(minutes=35),
                    ))
        if not db.scalar(select(StaffTask.id).where(
            StaffTask.tenant_id == tenant.id,
            StaffTask.restaurant_id == restaurant.id,
            StaffTask.status.in_(["pending", "acknowledged"]),
        )):
            table_t02_id = db.scalar(select(DiningTable.id).where(
                DiningTable.tenant_id == tenant.id,
                DiningTable.restaurant_id == restaurant.id,
                DiningTable.name == "T02",
            ))
            table_t09_id = db.scalar(select(DiningTable.id).where(
                DiningTable.tenant_id == tenant.id,
                DiningTable.restaurant_id == restaurant.id,
                DiningTable.name == "T09",
            ))
            first_order_id = db.scalar(select(RestaurantOrder.id).where(
                RestaurantOrder.tenant_id == tenant.id,
                RestaurantOrder.restaurant_id == restaurant.id,
            ).order_by(RestaurantOrder.created_at))
            db.add_all([
                StaffTask(
                    tenant_id=tenant.id,
                    restaurant_id=restaurant.id,
                    table_id=table_t09_id,
                    task_type="clean_table",
                    target_role="cleaning",
                    status="pending",
                    title="Clean table T09 after guest departure",
                    details={"source": "demo_seed"},
                ),
                StaffTask(
                    tenant_id=tenant.id,
                    restaurant_id=restaurant.id,
                    order_id=first_order_id,
                    task_type="serve_order",
                    target_role="waiter",
                    status="acknowledged",
                    title="Serve biryani order to T02",
                    details={"source": "demo_seed"},
                ),
                StaffTask(
                    tenant_id=tenant.id,
                    restaurant_id=restaurant.id,
                    table_id=table_t02_id,
                    order_id=first_order_id,
                    task_type="billing_followup",
                    target_role="cashier",
                    status="pending",
                    title="Bill follow-up for T02",
                    details={"source": "demo_seed"},
                ),
            ])
        today = now_utc().date()
        if not db.scalar(select(FestivalCalendar.id).where(
            FestivalCalendar.tenant_id == tenant.id,
            FestivalCalendar.restaurant_id.is_(None),
            FestivalCalendar.name == "Hyderabad Food Festival",
            FestivalCalendar.starts_on <= today,
            FestivalCalendar.ends_on >= today,
        )):
            db.add(FestivalCalendar(
                tenant_id=tenant.id,
                restaurant_id=None,
                state_code="TS",
                name="Hyderabad Food Festival",
                starts_on=today - timedelta(days=1),
                ends_on=today + timedelta(days=1),
                notes="Seeded demo festival for demand-aware recommendation examples.",
            ))
        db.commit()
        print(
            f"Demo organization {tenant.id} ready; Hyderabad outlet, 30 menu items, "
            "sample orders, and staff tasks seeded."
        )


if __name__ == "__main__":
    seed_demo()
    seed_platform_admin()
