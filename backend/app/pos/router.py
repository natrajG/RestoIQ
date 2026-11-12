import hashlib
import secrets
from uuid import uuid4
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.auth.dependencies import Principal, current_principal, has_outlet_access, require_roles
from app.core.audit import audit
from app.core.events import add_business_event
from app.core.subscriptions import current_plan_name
from app.ai_operations.service import create_staff_task
from app.db import get_db
from app.models import (
    Customer, CustomerLedgerEntry, DiningTable, MenuCategory, MenuItem, OperationalEvent, OrderItem, Payment,
    Refund, Restaurant, RestaurantOrder, LoyaltyEntry,
)
from app.pos.schemas import (
    MenuItemInput, OrderEventInput, OrderInput, PaymentInput, RefundInput, TableCorrectionInput,
)
from app.pos.service import (
    apply_charges, customer_for_phone, load_options, staff_name_of, money, next_bill_number, price_line, order_or_404, order_to_dict, outlet_or_404,
)

from app.integrations.providers.urbanpiper import publish_order_status  # noqa: E402

router = APIRouter(prefix="/api/v1", tags=["pos"])
MANAGERS = ("owner", "manager", "admin")
ORDER_ROLES = (*MANAGERS, "waiter", "server", "cashier", "kitchen", "cleaning")
ORDER_TAKER_ROLES = (*MANAGERS, "waiter", "server", "cashier")


@router.get("/outlets")
def list_outlets(db: Session = Depends(get_db), principal: Principal = Depends(current_principal)):
    rows = db.scalars(select(Restaurant).where(Restaurant.tenant_id == principal.tenant_id).order_by(Restaurant.name)).all()
    plan_name = current_plan_name(db, principal.tenant_id)
    return [{
        "id": r.id, "name": r.name, "timezone": r.timezone, "currency": r.currency,
        "state_code": r.state_code, "tax_config": r.tax_config,
        "subscription_plan": plan_name,
    } for r in rows if has_outlet_access(db, principal, r.id)]


@router.get("/outlets/{outlet_id}/tables")
def list_tables(outlet_id: int, db: Session = Depends(get_db), principal: Principal = Depends(current_principal)):
    outlet_or_404(db, principal, outlet_id)
    rows = db.scalars(select(DiningTable).where(
        DiningTable.restaurant_id == outlet_id, DiningTable.tenant_id == principal.tenant_id,
    ).order_by(DiningTable.name)).all()
    return [{"id": t.id, "name": t.name, "floor_id": t.floor_id, "seats": t.seats,
             "x": t.x, "y": t.y, "status": t.status} for t in rows]


@router.post("/outlets/{outlet_id}/tables/{table_id}/correction")
def correct_table(
    outlet_id: int,
    table_id: int,
    body: TableCorrectionInput,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles(*MANAGERS, "cleaning", "cleaner", "waiter", "server")),
):
    outlet_or_404(db, principal, outlet_id)
    table = db.scalar(select(DiningTable).where(
        DiningTable.id == table_id, DiningTable.restaurant_id == outlet_id,
        DiningTable.tenant_id == principal.tenant_id,
    ))
    if not table:
        raise HTTPException(404, "Table not found")
    table.status = body.status
    db.add(add_business_event(
        db, principal.tenant_id, outlet_id, "TABLE_STATE_CORRECTED", "staff",
        table_id=table.id, payload={"status": body.status, "reason": body.reason},
        idempotency_key=f"table:{table.id}:correction:{uuid4().hex}",
    ))
    if body.status == "DIRTY":
        create_staff_task(
            db, principal, outlet_id, "clean_table", "cleaning",
            f"Clean table {table.name}", table_id=table.id, details={"reason": body.reason},
        )
    audit(db, principal, "table_state_corrected", "table", table.id, {"status": body.status, "reason": body.reason})
    return {"id": table.id, "status": table.status, "evidence_source": "staff"}


@router.get("/outlets/{outlet_id}/menu")
def menu_items(outlet_id: int, db: Session = Depends(get_db), principal: Principal = Depends(current_principal)):
    outlet_or_404(db, principal, outlet_id)
    rows = db.scalars(select(MenuItem).where(
        MenuItem.restaurant_id == outlet_id, MenuItem.tenant_id == principal.tenant_id,
    ).order_by(MenuItem.name)).all()
    options = load_options(db, principal.tenant_id, {i.id for i in rows})
    return [{
        "id": i.id, "category_id": i.category_id, "name": i.name, "sku": i.sku,
        "price": str(i.price), "cost_price": str(i.cost_price) if i.cost_price is not None else None,
        "tax_rate": str(i.tax_rate), "active": i.active,
        "variants": [{"id": o.id, "name": o.name, "price": str(o.price)} for o in options.get(i.id, []) if o.kind == "variant"],
        "addons": [{"id": o.id, "name": o.name, "price": str(o.price)} for o in options.get(i.id, []) if o.kind == "addon"],
    } for i in rows]


@router.get("/outlets/{outlet_id}/menu/categories")
def menu_categories(outlet_id: int, db: Session = Depends(get_db), principal: Principal = Depends(current_principal)):
    outlet_or_404(db, principal, outlet_id)
    rows = db.scalars(select(MenuCategory).where(
        MenuCategory.restaurant_id == outlet_id, MenuCategory.tenant_id == principal.tenant_id,
    ).order_by(MenuCategory.sort_order, MenuCategory.name)).all()
    return [{"id": c.id, "name": c.name, "sort_order": c.sort_order} for c in rows]


@router.post("/outlets/{outlet_id}/menu/items", status_code=201)
def create_menu_item(
    outlet_id: int,
    body: MenuItemInput,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles(*MANAGERS)),
):
    outlet_or_404(db, principal, outlet_id)
    if body.restaurant_id != outlet_id:
        raise HTTPException(422, "Outlet ID mismatch")
    if body.category_id and not db.scalar(select(MenuCategory.id).where(
        MenuCategory.id == body.category_id, MenuCategory.restaurant_id == outlet_id,
        MenuCategory.tenant_id == principal.tenant_id,
    )):
        raise HTTPException(404, "Menu category not found")
    item = MenuItem(
        tenant_id=principal.tenant_id, restaurant_id=outlet_id, category_id=body.category_id,
        name=body.name, sku=body.sku, price=body.price, cost_price=body.cost_price, tax_rate=body.tax_rate,
    )
    db.add(item)
    db.flush()
    audit(db, principal, "menu_item_created", "menu_item", item.id)
    return {"id": item.id, "name": item.name, "sku": item.sku, "price": str(item.price)}


@router.get("/outlets/{outlet_id}/orders")
def list_orders(
    outlet_id: int,
    limit: int = 50,
    db: Session = Depends(get_db),
    principal: Principal = Depends(current_principal),
):
    outlet_or_404(db, principal, outlet_id)
    rows = db.scalars(select(RestaurantOrder).where(
        RestaurantOrder.restaurant_id == outlet_id, RestaurantOrder.tenant_id == principal.tenant_id,
    ).order_by(RestaurantOrder.created_at.desc()).limit(min(max(limit, 1), 200))).all()
    return [order_to_dict(o) for o in rows]


@router.post("/outlets/{outlet_id}/orders", status_code=201)
def create_order(
    outlet_id: int,
    body: OrderInput,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles(*ORDER_TAKER_ROLES)),
):
    outlet = outlet_or_404(db, principal, outlet_id)
    if body.restaurant_id != outlet_id:
        raise HTTPException(422, "Outlet ID mismatch")
    payload_hash = hashlib.sha256(body.model_dump_json(exclude_none=True).encode()).hexdigest()
    if idempotency_key:
        if len(idempotency_key) > 160:
            raise HTTPException(422, "Idempotency-Key must be at most 160 characters")
        # Serialise concurrent retries of the same key so the loser sees the winner's order.
        db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"order:{principal.tenant_id}:{idempotency_key}"})
        previous = db.scalar(select(RestaurantOrder).where(
            RestaurantOrder.tenant_id == principal.tenant_id,
            RestaurantOrder.idempotency_key == idempotency_key,
        ))
        if previous:
            placed = db.scalar(select(OperationalEvent).where(
                OperationalEvent.tenant_id == principal.tenant_id, OperationalEvent.idempotency_key == f"order:{previous.id}:placed"))
            stored = (placed.payload or {}).get("payload_hash") if placed else None
            if previous.restaurant_id != outlet_id or (stored and stored != payload_hash):
                raise HTTPException(409, "Idempotency-Key was already used for a different order")
            return order_to_dict(previous)
    if body.order_type == "dine_in" and not body.table_id:
        raise HTTPException(422, "Dine-in orders require a table")
    if body.order_type == "delivery" and not (body.contact_phone and body.delivery_address and body.delivery_address.strip()):
        raise HTTPException(422, "Delivery orders need a phone number and address")
    if body.order_type != "dine_in" and body.table_id:
        raise HTTPException(422, "Takeaway and delivery orders do not use a table")
    table = None
    if body.table_id:
        table = db.scalar(select(DiningTable).where(
            DiningTable.id == body.table_id, DiningTable.restaurant_id == outlet_id,
            DiningTable.tenant_id == principal.tenant_id,
        ).with_for_update())
        if not table:
            raise HTTPException(404, "Table not found")
        if table.status not in {"FREE", "READY"}:
            raise HTTPException(409, f"Table is not available ({table.status})")
    if body.customer_id and not db.scalar(select(Customer.id).where(
        Customer.id == body.customer_id, Customer.restaurant_id == outlet_id,
        Customer.tenant_id == principal.tenant_id,
    )):
        raise HTTPException(404, "Customer not found")

    item_ids = {line.menu_item_id for line in body.items}
    menu = db.scalars(select(MenuItem).where(
        MenuItem.id.in_(item_ids), MenuItem.restaurant_id == outlet_id,
        MenuItem.tenant_id == principal.tenant_id, MenuItem.active.is_(True),
    )).all()
    by_id = {item.id: item for item in menu}
    if item_ids != set(by_id):
        raise HTTPException(422, "One or more menu items are missing or unavailable")
    composition = (outlet.tax_config or {}).get("gst_scheme") == "composition"
    rate_of = lambda i: Decimal("0") if composition else i.tax_rate  # composition dealers cannot charge GST
    if body.scheduled_for or body.advance_amount:
        if body.order_type == "dine_in":
            raise HTTPException(422, "Advance orders are for takeaway or delivery")
        if body.scheduled_for and body.scheduled_for < datetime.now(timezone.utc) - timedelta(minutes=5):
            raise HTTPException(422, "Scheduled time is in the past")
    if body.discount_amount > 0 and principal.role not in (*MANAGERS, "cashier"):
        raise HTTPException(403, "Only an owner, manager or cashier can give a discount")

    customer_id = body.customer_id
    if not customer_id:
        known = customer_for_phone(db, principal.tenant_id, outlet_id, body.contact_phone, body.contact_name)
        customer_id = known.id if known else None
    order = RestaurantOrder(
        tenant_id=principal.tenant_id, restaurant_id=outlet_id, table_id=body.table_id,
        customer_id=customer_id, covers=body.covers, staff_name=staff_name_of(db, principal),
        remark=(body.remark or "").strip() or None,
        order_number=next_bill_number(db, principal.tenant_id, outlet_id, outlet.timezone),
        idempotency_key=idempotency_key, order_type=body.order_type,
        contact_name=(body.contact_name or "").strip() or None, contact_phone=body.contact_phone,
        delivery_address=(body.delivery_address or "").strip() or None,
        status="submitted", source="native_pos", scheduled_for=body.scheduled_for,
        discount_type="fixed" if body.discount_amount > 0 else None, discount_value=body.discount_amount,
    )
    options = load_options(db, principal.tenant_id, set(by_id))
    for line in body.items:
        item = by_id[line.menu_item_id]
        unit, name, variant_name, addons = price_line(item, options[item.id], line.variant_id, line.addon_ids)
        base = money(unit * line.quantity)
        line_tax = money(base * rate_of(item) / Decimal("100"))
        order.items.append(OrderItem(
            tenant_id=principal.tenant_id, menu_item_id=item.id, item_name=name,
            quantity=line.quantity, unit_price=unit, tax_rate=rate_of(item),
            line_total=base + line_tax, notes=line.notes, status="active",
            variant_name=variant_name, addons=addons or None,
        ))
    try:
        apply_charges(order, outlet)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    db.add(order)
    db.flush()
    if table:
        table.status = "OCCUPIED"
    if body.advance_amount:
        if body.advance_amount > order.total:
            raise HTTPException(422, "Advance cannot be more than the order total")
        db.add(Payment(tenant_id=principal.tenant_id, order_id=order.id, method=body.advance_method, status="recorded",
                       amount=money(body.advance_amount), reference="advance", idempotency_key=f"advance:{order.id}"))
    db.add(add_business_event(
        db, principal.tenant_id, outlet_id, "ORDER_PLACED", "native_pos",
        order_id=order.id, table_id=body.table_id,
        payload={"order_number": order.order_number, "items": len(body.items), "payload_hash": payload_hash},
        idempotency_key=f"order:{order.id}:placed",
    ))
    create_staff_task(
        db, principal, outlet_id, "prepare_order", "kitchen",
        f"Prepare order {order.order_number}",
        table_id=body.table_id, order_id=order.id,
    )
    audit(db, principal, "order_created", "order", order.id, {"order_type": order.order_type})
    return order_to_dict(order)


@router.get("/orders/{order_id}")
def get_order(order_id: int, db: Session = Depends(get_db), principal: Principal = Depends(current_principal)):
    return order_to_dict(order_or_404(db, principal, order_id))


@router.post("/orders/{order_id}/events")
def update_order_event(
    order_id: int,
    body: OrderEventInput,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles(*ORDER_ROLES)),
):
    order = order_or_404(db, principal, order_id)
    outlet = outlet_or_404(db, principal, order.restaurant_id)
    if order.status in {"cancelled", "refunded"}:
        raise HTTPException(409, f"Cannot update a {order.status} order")
    status_by_event = {
        "KOT_ACCEPTED": "accepted", "PREPARATION_STARTED": "preparing", "FOOD_READY": "ready",
        "FOOD_PICKED_UP": "picked_up", "FOOD_DELIVERED": "served",
        "BILL_REQUESTED": "bill_requested", "ORDER_COMPLETED": "completed",
        "CUSTOMER_DEPARTED": "completed",
    }
    allowed_from = {
        "KOT_ACCEPTED": {"submitted"},
        "PREPARATION_STARTED": {"accepted", "submitted"},
        "FOOD_READY": {"preparing"},
        "FOOD_PICKED_UP": {"ready"},
        "FOOD_DELIVERED": {"picked_up", "ready"},
        "BILL_REQUESTED": {"served", "completed", "paid", "bill_requested"},
        "ORDER_COMPLETED": {"served", "bill_requested", "completed", "paid"},
        "CUSTOMER_DEPARTED": {"served", "bill_requested", "completed", "paid"},
    }
    if order.status not in allowed_from[body.event_type]:
        raise HTTPException(409, f"{body.event_type} is not valid while order is {order.status}")
    if body.event_type == "CUSTOMER_DEPARTED" and order.table_id:
        table = db.get(DiningTable, order.table_id)
        if table and table.tenant_id == principal.tenant_id:
            table.status = "DIRTY"
    elif body.event_type == "BILL_REQUESTED" and order.table_id:
        table = db.get(DiningTable, order.table_id)
        if table and table.tenant_id == principal.tenant_id:
            table.status = "BILLING"
    if body.event_type not in {"CUSTOMER_DEPARTED", "ORDER_COMPLETED"}:
        order.status = status_by_event[body.event_type]
    db.add(add_business_event(
        db, principal.tenant_id, order.restaurant_id, body.event_type, "native_pos",
        order_id=order.id, table_id=order.table_id,
        payload={"notes": body.notes} if body.notes else {},
        idempotency_key=f"order:{order.id}:{body.event_type}:{uuid4().hex}",
    ))
    if body.event_type == "FOOD_READY":
        create_staff_task(
            db, principal, order.restaurant_id, "serve_order", "waiter",
            f"Pick up order {order.order_number} and serve "
            + (f"table {t.name}" if order.table_id and (t := db.get(DiningTable, order.table_id)) else order.order_type.replace("_", " ")),
            table_id=order.table_id, order_id=order.id,
        )
    elif body.event_type == "CUSTOMER_DEPARTED" and order.table_id:
        table = db.get(DiningTable, order.table_id)
        create_staff_task(
            db, principal, order.restaurant_id, "clean_table", "cleaning",
            f"Clean table {table.name if table else order.table_id}",
            table_id=order.table_id, order_id=order.id,
        )
    elif body.event_type == "BILL_REQUESTED":
        create_staff_task(
            db, principal, order.restaurant_id, "prepare_bill", "cashier",
            f"Prepare bill for order {order.order_number}",
            table_id=order.table_id, order_id=order.id,
        )
    if body.event_type == "FOOD_READY":
        publish_order_status(db, order, "Food Ready")
    audit(db, principal, "order_event_recorded", "order", order.id, {"event_type": body.event_type})
    return order_to_dict(order)


@router.get("/outlets/{outlet_id}/kitchen")
def kitchen_queue(outlet_id: int, db: Session = Depends(get_db), principal: Principal = Depends(current_principal)):
    outlet_or_404(db, principal, outlet_id)
    rows = db.scalars(select(RestaurantOrder).where(
        RestaurantOrder.restaurant_id == outlet_id, RestaurantOrder.tenant_id == principal.tenant_id,
        RestaurantOrder.status.in_(["submitted", "preparing", "ready"]),
    ).order_by(RestaurantOrder.created_at)).all()
    return [order_to_dict(o) for o in rows]


@router.post("/orders/{order_id}/payments", status_code=201)
def record_payment(
    order_id: int,
    body: PaymentInput,
    response: Response,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=160),
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles(*ORDER_TAKER_ROLES)),
):
    if not idempotency_key.strip():
        raise HTTPException(422, "Idempotency-Key cannot be blank")
    order = order_or_404(db, principal, order_id, for_update=True)
    outlet = outlet_or_404(db, principal, order.restaurant_id)
    previous = db.scalar(select(Payment).where(
        Payment.tenant_id == principal.tenant_id,
        Payment.order_id == order.id,
        Payment.idempotency_key == idempotency_key,
    ))
    if previous:
        if (
            previous.method != body.method
            or previous.amount != money(body.amount)
            or previous.reference != body.reference
        ):
            raise HTTPException(409, "Idempotency-Key was already used for a different payment")
        response.status_code = 200
        return {
            "id": previous.id, "order_id": order.id, "amount": str(previous.amount),
            "method": previous.method, "status": previous.status, "order_paid": order.status == "paid",
        }
    if order.status in {"paid", "cancelled", "refunded"}:
        raise HTTPException(409, f"Cannot accept payment for a {order.status} order")
    paid = db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).where(
        Payment.order_id == order.id, Payment.tenant_id == principal.tenant_id, Payment.status == "recorded",
    )) or Decimal("0")
    refunded = db.scalar(select(func.coalesce(func.sum(Refund.amount), 0)).where(
        Refund.order_id == order.id, Refund.tenant_id == principal.tenant_id, Refund.status == "recorded",
    )) or Decimal("0")
    payable = money(order.total + order.tip)
    if money(Decimal(paid) - Decimal(refunded) + body.amount) > payable:
        raise HTTPException(422, "Payment exceeds the outstanding order balance")
    payment = Payment(
        tenant_id=principal.tenant_id, order_id=order.id, method=body.method,
        status="recorded", amount=money(body.amount), reference=body.reference,
        idempotency_key=idempotency_key,
    )
    db.add(payment)
    db.flush()
    if body.method == "customer_account":
        if not order.customer_id:
            raise HTTPException(422, "Add the customer's phone on the order to put the bill on their account")
        db.add(CustomerLedgerEntry(
            tenant_id=principal.tenant_id, restaurant_id=order.restaurant_id, customer_id=order.customer_id,
            kind="debit", amount=money(body.amount), method="account", order_id=order.id,
            remark=f"Bill {order.order_number}", created_by=staff_name_of(db, principal)))
    fully_paid = money(Decimal(paid) - Decimal(refunded) + body.amount) == payable
    if fully_paid:
        order.status = "paid"
        if order.customer_id:
            customer = db.get(Customer, order.customer_id)
            if customer and customer.tenant_id == principal.tenant_id:
                points = int(order.total)
                customer.loyalty_points += points
                db.add(LoyaltyEntry(
                    tenant_id=principal.tenant_id, restaurant_id=order.restaurant_id,
                    customer_id=customer.id, order_id=order.id, points_delta=points,
                    reason="purchase",
                ))
        db.add(add_business_event(
            db, principal.tenant_id, order.restaurant_id, "PAYMENT_COMPLETED", "native_pos",
            order_id=order.id, table_id=order.table_id,
            payload={"payment_method": body.method, "amount": str(order.total)},
            idempotency_key=f"order:{order.id}:payment-completed",
        ))
    audit(db, principal, "payment_recorded", "payment", payment.id, {"method": body.method, "amount": str(body.amount)})
    return {"id": payment.id, "order_id": order.id, "amount": str(payment.amount),
            "method": payment.method, "status": payment.status, "order_paid": fully_paid}


@router.post("/orders/{order_id}/refunds", status_code=201)
def refund_order(
    order_id: int,
    body: RefundInput,
    response: Response,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=160),
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles(*MANAGERS)),
):
    if not idempotency_key.strip():
        raise HTTPException(422, "Idempotency-Key cannot be blank")
    order = order_or_404(db, principal, order_id, for_update=True)
    outlet = outlet_or_404(db, principal, order.restaurant_id)
    previous = db.scalar(select(Refund).where(
        Refund.tenant_id == principal.tenant_id,
        Refund.order_id == order.id,
        Refund.idempotency_key == idempotency_key,
    ))
    if previous:
        if previous.amount != money(body.amount) or previous.reason != body.reason:
            raise HTTPException(409, "Idempotency-Key was already used for a different refund")
        response.status_code = 200
        return {
            "id": previous.id, "order_id": order.id, "amount": str(previous.amount),
            "status": previous.status, "gateway_refund_processed": False,
        }
    paid = db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).where(
        Payment.order_id == order.id, Payment.tenant_id == principal.tenant_id, Payment.status == "recorded",
    )) or Decimal("0")
    existing = db.scalar(select(func.coalesce(func.sum(Refund.amount), 0)).where(
        Refund.order_id == order.id, Refund.tenant_id == principal.tenant_id, Refund.status == "recorded",
    )) or Decimal("0")
    if db.scalar(select(func.count()).select_from(Payment).where(
            Payment.order_id == order.id, Payment.tenant_id == principal.tenant_id, Payment.method == "customer_account")):
        raise HTTPException(409, "This bill was put on a customer account. Record a credit on the customer's account instead")
    if body.amount > Decimal(paid) - Decimal(existing):
        raise HTTPException(422, "Refund exceeds the unrefunded recorded payments")
    refund = Refund(
        tenant_id=principal.tenant_id, order_id=order.id, amount=money(body.amount),
        reason=body.reason, created_by=principal.user_id, idempotency_key=idempotency_key,
    )
    db.add(refund)
    db.flush()
    if money(Decimal(existing) + body.amount) == money(Decimal(paid)):
        order.status = "refunded"
    db.add(add_business_event(
        db, principal.tenant_id, order.restaurant_id, "REFUND_RECORDED", "native_pos",
        order_id=order.id, payload={"amount": str(body.amount), "reason": body.reason},
        idempotency_key=f"refund:{refund.id}",
    ))
    audit(db, principal, "refund_recorded", "refund", refund.id, {"amount": str(body.amount), "reason": body.reason})
    return {"id": refund.id, "order_id": order.id, "amount": str(refund.amount),
            "status": refund.status, "gateway_refund_processed": False}


@router.get("/outlets/{outlet_id}/customers")
def list_customers(outlet_id: int, db: Session = Depends(get_db), principal: Principal = Depends(current_principal)):
    outlet_or_404(db, principal, outlet_id)
    rows = db.scalars(select(Customer).where(
        Customer.restaurant_id == outlet_id, Customer.tenant_id == principal.tenant_id,
    ).order_by(Customer.name)).all()
    return [{"id": c.id, "name": c.name, "phone": c.phone, "email": c.email,
             "loyalty_points": c.loyalty_points} for c in rows]


@router.get("/outlets/{outlet_id}/analytics/summary")
def analytics_summary(outlet_id: int, db: Session = Depends(get_db), principal: Principal = Depends(current_principal)):
    outlet = outlet_or_404(db, principal, outlet_id)
    now_local = datetime.now(ZoneInfo(outlet.timezone))
    start = datetime.combine(now_local.date(), time.min, tzinfo=ZoneInfo(outlet.timezone)).astimezone(timezone.utc)
    paid = db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0))
        .join(RestaurantOrder, RestaurantOrder.id == Payment.order_id)
        .where(
            Payment.tenant_id == principal.tenant_id, Payment.status == "recorded",
            RestaurantOrder.restaurant_id == outlet_id, Payment.created_at >= start,
        )
    ) or Decimal("0")
    refunds = db.scalar(
        select(func.coalesce(func.sum(Refund.amount), 0))
        .join(RestaurantOrder, RestaurantOrder.id == Refund.order_id)
        .where(
            Refund.tenant_id == principal.tenant_id, Refund.status == "recorded",
            RestaurantOrder.restaurant_id == outlet_id, Refund.created_at >= start,
        )
    ) or Decimal("0")
    orders_today = db.scalar(select(func.count(RestaurantOrder.id)).where(
        RestaurantOrder.tenant_id == principal.tenant_id, RestaurantOrder.restaurant_id == outlet_id,
        RestaurantOrder.created_at >= start,
    )) or 0
    active_tables = db.scalar(select(func.count(DiningTable.id)).where(
        DiningTable.tenant_id == principal.tenant_id, DiningTable.restaurant_id == outlet_id,
        DiningTable.status.in_(["OCCUPIED", "BILLING"]),
    )) or 0
    total_tables = db.scalar(select(func.count(DiningTable.id)).where(
        DiningTable.tenant_id == principal.tenant_id, DiningTable.restaurant_id == outlet_id,
    )) or 0
    return {
        "currency": outlet.currency, "local_date": now_local.date().isoformat(),
        "gross_payments_actual": str(money(Decimal(paid))),
        "refunds_actual": str(money(Decimal(refunds))),
        "net_collections_actual": str(money(Decimal(paid) - Decimal(refunds))),
        "orders_today": orders_today, "active_tables": active_tables, "total_tables": total_tables,
        "estimated_opportunity": None,
    }
