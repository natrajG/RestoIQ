from decimal import Decimal
from decimal import ROUND_HALF_UP

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import Principal, require_outlet_access
from app.models import MenuItem, MenuOption, Restaurant, RestaurantOrder
from app.pos.repository import order_by_id

CENT = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_order_totals(
    items: list[tuple[int, Decimal, Decimal]], discount: Decimal,
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    subtotal = sum((Decimal(quantity) * price for quantity, price, _ in items), Decimal("0"))
    tax = sum(
        (money(Decimal(quantity) * price * rate / Decimal("100")) for quantity, price, rate in items),
        Decimal("0"),
    )
    subtotal, tax, discount = money(subtotal), money(tax), money(discount)
    if discount > subtotal + tax:
        raise ValueError("Discount cannot exceed the order total")
    return subtotal, tax, discount, money(subtotal + tax - discount)


def require_outlet(db: Session, principal: Principal, outlet_id: int) -> Restaurant:
    return require_outlet_access(db, principal, outlet_id)


outlet_or_404 = require_outlet


def require_order(
    db: Session, principal: Principal, order_id: int, for_update: bool = False,
) -> RestaurantOrder:
    order = order_by_id(db, principal.tenant_id, order_id, for_update=for_update)
    if not order:
        raise HTTPException(404, "Order not found")
    require_outlet(db, principal, order.restaurant_id)
    return order


order_or_404 = require_order


def order_to_dict(order: RestaurantOrder) -> dict:
    return {
        "id": order.id, "order_number": order.order_number, "restaurant_id": order.restaurant_id,
        "table_id": order.table_id, "customer_id": order.customer_id, "order_type": order.order_type,
        "contact_name": order.contact_name, "contact_phone": order.contact_phone, "delivery_address": order.delivery_address,
        "status": order.status, "source": order.source, "subtotal": str(order.subtotal),
        "tax_total": str(order.tax_total), "discount_total": str(order.discount_total),
        "total": str(order.total), "created_at": order.created_at,
        "service_charge": str(order.service_charge), "round_off": str(order.round_off), "tip": str(order.tip),
        "payable": str(money(order.total + order.tip)), "discount_type": order.discount_type,
        "discount_value": str(order.discount_value), "discount_reason": order.discount_reason,
        "service_charge_waived": order.service_charge_waived,
        "covers": order.covers, "remark": order.remark, "staff_name": order.staff_name,
        "scheduled_for": order.scheduled_for, "complimentary_reason": order.complimentary_reason,
        "complimentary_total": str(money(sum((Decimal(i.quantity) * i.unit_price for i in order.active_items if i.complimentary), Decimal("0")))),
        "items": [
            {"id": item.id, "menu_item_id": item.menu_item_id, "name": item.item_name,
             "quantity": item.quantity, "unit_price": str(item.unit_price),
             "line_total": str(item.line_total), "notes": item.notes,
             "kot_no": item.kot_no, "status": item.status, "cancel_reason": item.cancel_reason,
             "addons": item.addons or [], "complimentary": item.complimentary}
            for item in order.items
        ],
    }


def calculate_totals(lines: list[tuple[int, Decimal, Decimal]], discount: Decimal):
    return calculate_order_totals(lines, discount), money


def next_bill_number(db: Session, tenant_id: int, outlet_id: int, tz: str) -> str:
    """Consecutive per outlet and Indian financial year (Apr-Mar), as GST invoices require."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from sqlalchemy import text

    now = datetime.now(ZoneInfo(tz))
    start = now.year if now.month >= 4 else now.year - 1
    fy = f"{start % 100:02d}{(start + 1) % 100:02d}"
    number = db.execute(text(
        "INSERT INTO document_counters (tenant_id, restaurant_id, fy, last_number) VALUES (:t, :o, :fy, 1) "
        "ON CONFLICT (restaurant_id, fy) DO UPDATE SET last_number = document_counters.last_number + 1 "
        "RETURNING last_number"), {"t": tenant_id, "o": outlet_id, "fy": fy}).scalar_one()
    return f"O{outlet_id}/{fy}/{number:06d}"


def _allocate(amount: Decimal, weights: list[Decimal]) -> list[Decimal]:
    """Split a money amount in proportion to weights; the last share absorbs rounding."""
    total = sum(weights, Decimal("0"))
    if total <= 0:
        return [Decimal("0")] * len(weights)
    shares, used = [], Decimal("0")
    for w in weights[:-1]:
        share = money(amount * w / total)
        shares.append(share)
        used += share
    return shares + [money(amount - used)]


def compute_charges(
    lines: list[tuple[Decimal, Decimal]], discount_type: str | None, discount_value: Decimal,
    service_pct: Decimal, waive_service: bool, round_on: bool,
) -> dict:
    """lines are (taxable base, GST rate). A discount before supply and service charge both
    change the taxable value, and GST is charged per rate slab on that value."""
    by_rate: dict[Decimal, Decimal] = {}
    for base, rate in lines:
        by_rate[rate] = by_rate.get(rate, Decimal("0")) + base
    rates = sorted(by_rate)
    bases = [money(by_rate[r]) for r in rates]
    subtotal = sum(bases, Decimal("0"))
    if discount_type == "percent":
        if discount_value > 100:
            raise ValueError("Discount cannot exceed 100%")
        discount = money(subtotal * discount_value / Decimal("100"))
    elif discount_type == "fixed":
        discount = money(discount_value)
    else:
        discount = Decimal("0")
    if not lines:
        discount = Decimal("0")
    if discount > subtotal:
        raise ValueError("Discount cannot exceed the order subtotal")
    nets = [b - d for b, d in zip(bases, _allocate(discount, bases))]
    service = Decimal("0") if waive_service else money((subtotal - discount) * service_pct / Decimal("100"))
    taxable = [n + sv for n, sv in zip(nets, _allocate(service, nets))]
    slabs = [(r, t, money(t * r / Decimal("100"))) for r, t in zip(rates, taxable)]
    tax = sum((x[2] for x in slabs), Decimal("0"))
    before_round = subtotal - discount + service + tax
    total = before_round.quantize(Decimal("1"), rounding=ROUND_HALF_UP) if round_on else before_round
    return {"subtotal": subtotal, "discount": discount, "service_charge": service, "tax": tax,
            "slabs": slabs, "round_off": money(total - before_round), "total": money(total)}


def order_charges(order: RestaurantOrder, outlet: Restaurant) -> dict:
    cfg = outlet.tax_config or {}
    return compute_charges(
        [(money(Decimal(i.quantity) * i.unit_price), i.tax_rate) for i in order.active_items if not i.complimentary],
        order.discount_type, order.discount_value, Decimal(str(cfg.get("service_charge_pct", 0))),
        order.service_charge_waived, bool(cfg.get("round_off", False)),
    )


def apply_charges(order: RestaurantOrder, outlet: Restaurant) -> dict:
    """Recompute and store every money field of the order. Raises ValueError for invalid discounts."""
    c = order_charges(order, outlet)
    order.subtotal, order.discount_total, order.service_charge = c["subtotal"], c["discount"], c["service_charge"]
    order.tax_total, order.round_off, order.total = c["tax"], c["round_off"], c["total"]
    return c


def load_options(db: Session, tenant_id: int, item_ids: set[int]) -> dict[int, list[MenuOption]]:
    out: dict[int, list[MenuOption]] = {i: [] for i in item_ids}
    for o in db.scalars(select(MenuOption).where(
            MenuOption.tenant_id == tenant_id, MenuOption.menu_item_id.in_(item_ids), MenuOption.active.is_(True))):
        out[o.menu_item_id].append(o)
    return out


def price_line(item: MenuItem, options: list[MenuOption], variant_id: int | None, addon_ids: list[int]):
    """Return (unit_price, item_name, variant_name, addons) for one order line, validating the choices."""
    variants = {o.id: o for o in options if o.kind == "variant"}
    addons = {o.id: o for o in options if o.kind == "addon"}
    if variants and variant_id is None:
        raise HTTPException(422, f"Choose a size/variant for {item.name}")
    if variant_id is not None and variant_id not in variants:
        raise HTTPException(422, f"Invalid variant for {item.name}")
    if len(set(addon_ids)) != len(addon_ids) or any(a not in addons for a in addon_ids):
        raise HTTPException(422, f"Invalid add-on for {item.name}")
    variant = variants.get(variant_id) if variant_id is not None else None
    chosen = [addons[a] for a in addon_ids]
    unit = (variant.price if variant else item.price) + sum((a.price for a in chosen), Decimal("0"))
    name = f"{item.name} ({variant.name})" if variant else item.name
    return money(unit), name, variant.name if variant else None, [{"name": a.name, "price": str(a.price)} for a in chosen]


def staff_name_of(db: Session, principal) -> str:
    from app.models import User
    user = db.get(User, principal.user_id)
    return (user.full_name or user.email.split("@")[0]) if user else "Staff"


def customer_for_phone(db: Session, tenant_id: int, outlet_id: int, phone: str | None, name: str | None):
    """Find (or create) the outlet's customer for an order's phone number so history builds up automatically."""
    from app.models import Customer
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())[-10:]
    if len(digits) < 7:
        return None
    rows = db.scalars(select(Customer).where(Customer.tenant_id == tenant_id, Customer.restaurant_id == outlet_id,
                                             Customer.phone.is_not(None))).all()
    for c in rows:
        if "".join(ch for ch in (c.phone or "") if ch.isdigit())[-10:] == digits:
            if name and (not c.name or c.name == "Guest"):
                c.name = name.strip()[:160]
            return c
    c = Customer(tenant_id=tenant_id, restaurant_id=outlet_id, name=(name or "Guest").strip()[:160] or "Guest", phone=phone)
    db.add(c)
    db.flush()
    return c
