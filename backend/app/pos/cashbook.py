import re
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from typing_extensions import Annotated

from app.auth.dependencies import Principal, current_principal, require_roles
from app.core.audit import audit
from app.db import get_db
from app.models import Customer, CustomerLedgerEntry, DayClose, Payment, PettyCashEntry, Refund, RestaurantOrder, now_utc
from app.pos.service import money, outlet_or_404, staff_name_of

router = APIRouter(prefix="/api/v1", tags=["cashbook"])
CASH_ROLES = ("owner", "manager", "admin", "cashier")
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


PETTY_CATEGORIES = ("Grocery", "Vegetables", "Dairy", "Beverages", "Bakery", "Packaging", "Stationery", "Housekeeping",
                    "Maintenance", "Gas & fuel", "Staff advance", "Vendor advance", "Stock transfer", "Other")


class PettyCashInput(BaseModel):
    kind: Annotated[str, StringConstraints(pattern="^(in|out)$")]
    category: Annotated[str, StringConstraints(pattern="^(" + "|".join(re.escape(c) for c in PETTY_CATEGORIES) + ")$")] = "Other"
    pay_method: Annotated[str, StringConstraints(pattern="^(cash|upi|card|bank)$")] = "cash"
    amount: Decimal = Field(gt=0, le=10_000_000, decimal_places=2)
    reason: Text


class DayCloseInput(BaseModel):
    business_date: date | None = None
    opening_cash: Decimal | None = Field(default=None, ge=0, le=100_000_000, decimal_places=2)
    counted_cash: Decimal = Field(ge=0, le=100_000_000, decimal_places=2)
    note: str | None = Field(default=None, max_length=300)


class CustomerInput(BaseModel):
    name: Text
    phone: str | None = Field(default=None, pattern=r"^[0-9+ -]{7,20}$")
    email: str | None = Field(default=None, max_length=254)
    birthday: date | None = None
    anniversary: date | None = None
    gstin: str | None = Field(default=None, pattern=r"^[0-9A-Za-z]{15}$")
    address: str | None = Field(default=None, max_length=400)


def _today(outlet) -> date:
    return datetime.now(ZoneInfo(outlet.timezone)).date()


def _window(outlet, day: date):
    tz = ZoneInfo(outlet.timezone)
    start = datetime.combine(day, time.min, tz)
    return start, start + timedelta(days=1)


def _summary(db: Session, principal: Principal, outlet, day: date) -> dict:
    start, end = _window(outlet, day)
    tid, oid = principal.tenant_id, outlet.id
    cash_in = db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).join(
        RestaurantOrder, RestaurantOrder.id == Payment.order_id).where(
        Payment.tenant_id == tid, RestaurantOrder.restaurant_id == oid, Payment.method == "cash",
        Payment.status == "recorded", Payment.created_at >= start, Payment.created_at < end)) or 0
    cash_refunds = db.scalar(select(func.coalesce(func.sum(Refund.amount), 0)).join(
        Payment, Payment.id == Refund.payment_id).join(RestaurantOrder, RestaurantOrder.id == Refund.order_id).where(
        Refund.tenant_id == tid, RestaurantOrder.restaurant_id == oid, Payment.method == "cash",
        Refund.status == "recorded", Refund.created_at >= start, Refund.created_at < end)) or 0
    entries = db.scalars(select(PettyCashEntry).where(
        PettyCashEntry.tenant_id == tid, PettyCashEntry.restaurant_id == oid, PettyCashEntry.business_date == day,
    ).order_by(PettyCashEntry.id)).all()
    # Only cash entries move the drawer; other pay methods are recorded but do not change the cash count.
    petty_in = sum((e.amount for e in entries if e.kind == "in" and e.pay_method == "cash"), Decimal("0"))
    petty_out = sum((e.amount for e in entries if e.kind == "out" and e.pay_method == "cash"), Decimal("0"))
    account_cash = db.scalar(select(func.coalesce(func.sum(CustomerLedgerEntry.amount), 0)).where(
        CustomerLedgerEntry.tenant_id == tid, CustomerLedgerEntry.restaurant_id == oid, CustomerLedgerEntry.kind == "credit",
        CustomerLedgerEntry.method == "cash", CustomerLedgerEntry.created_at >= start, CustomerLedgerEntry.created_at < end)) or 0
    closed = db.scalar(select(DayClose).where(DayClose.restaurant_id == oid, DayClose.business_date == day))
    previous = db.scalar(select(DayClose).where(DayClose.restaurant_id == oid, DayClose.business_date < day)
                         .order_by(DayClose.business_date.desc()))
    opening = closed.opening_cash if closed else (previous.counted_cash if previous else Decimal("0"))
    cash_sales = money(Decimal(cash_in) - Decimal(cash_refunds) + Decimal(account_cash))
    expected = money(opening + cash_sales + petty_in - petty_out)
    unsettled = db.scalars(select(RestaurantOrder).where(
        RestaurantOrder.tenant_id == tid, RestaurantOrder.restaurant_id == oid,
        RestaurantOrder.status.notin_(("paid", "completed", "cancelled", "refunded")),
        RestaurantOrder.created_at < end,
        (RestaurantOrder.scheduled_for.is_(None)) | (RestaurantOrder.scheduled_for < end),
    ).order_by(RestaurantOrder.created_at)).all()
    open_orders = len(unsettled)
    return {
        "date": day.isoformat(), "opening_cash": str(opening), "opening_known": bool(previous or closed),
        "cash_sales": str(cash_sales), "petty_in": str(petty_in), "petty_out": str(petty_out),
        "expected_cash": str(expected), "unpaid_orders": open_orders, "account_cash": str(money(Decimal(account_cash))),
        "unsettled": [{"id": o.id, "order_number": o.order_number, "order_type": o.order_type, "total": str(o.total),
                       "status": o.status, "scheduled_for": o.scheduled_for} for o in unsettled],
        "categories": list(PETTY_CATEGORIES),
        "entries": [{"id": e.id, "kind": e.kind, "amount": str(e.amount), "reason": e.reason, "category": e.category, "pay_method": e.pay_method,
                     "created_by": e.created_by, "created_at": e.created_at} for e in entries],
        "closed": None if not closed else {
            "counted_cash": str(closed.counted_cash), "difference": str(closed.difference), "note": closed.note,
            "closed_by": closed.closed_by, "created_at": closed.created_at},
    }


@router.get("/outlets/{outlet_id}/cashbook")
def cashbook(outlet_id: int, day: date | None = None, db: Session = Depends(get_db),
             principal: Principal = Depends(require_roles(*CASH_ROLES))):
    outlet = outlet_or_404(db, principal, outlet_id)
    day = day or _today(outlet)
    if day > _today(outlet):
        raise HTTPException(422, "Date is in the future")
    return _summary(db, principal, outlet, day)


@router.post("/outlets/{outlet_id}/petty-cash", status_code=201)
def add_petty_cash(outlet_id: int, body: PettyCashInput, db: Session = Depends(get_db),
                   principal: Principal = Depends(require_roles(*CASH_ROLES))):
    outlet = outlet_or_404(db, principal, outlet_id)
    day = _today(outlet)
    if db.scalar(select(DayClose.id).where(DayClose.restaurant_id == outlet_id, DayClose.business_date == day)):
        raise HTTPException(409, "Today is already closed")
    entry = PettyCashEntry(tenant_id=principal.tenant_id, restaurant_id=outlet_id, business_date=day,
                           kind=body.kind, amount=money(body.amount), reason=body.reason, category=body.category, pay_method=body.pay_method,
                           created_by=staff_name_of(db, principal))
    db.add(entry)
    db.flush()
    audit(db, principal, "petty_cash_added", "petty_cash", entry.id, {"kind": body.kind, "amount": str(body.amount)})
    return _summary(db, principal, outlet, day)


@router.delete("/outlets/{outlet_id}/petty-cash/{entry_id}")
def delete_petty_cash(outlet_id: int, entry_id: int, db: Session = Depends(get_db),
                      principal: Principal = Depends(require_roles("owner", "manager", "admin"))):
    outlet = outlet_or_404(db, principal, outlet_id)
    entry = db.scalar(select(PettyCashEntry).where(PettyCashEntry.id == entry_id, PettyCashEntry.restaurant_id == outlet_id,
                                                    PettyCashEntry.tenant_id == principal.tenant_id))
    if not entry:
        raise HTTPException(404, "Entry not found")
    if db.scalar(select(DayClose.id).where(DayClose.restaurant_id == outlet_id, DayClose.business_date == entry.business_date)):
        raise HTTPException(409, "That day is already closed")
    db.delete(entry)
    audit(db, principal, "petty_cash_deleted", "petty_cash", entry_id, {"amount": str(entry.amount)})
    return _summary(db, principal, outlet, entry.business_date)


@router.post("/outlets/{outlet_id}/day-close", status_code=201)
def close_day(outlet_id: int, body: DayCloseInput, db: Session = Depends(get_db),
              principal: Principal = Depends(require_roles(*CASH_ROLES))):
    outlet = outlet_or_404(db, principal, outlet_id)
    day = body.business_date or _today(outlet)
    if day > _today(outlet):
        raise HTTPException(422, "Date is in the future")
    summary = _summary(db, principal, outlet, day)
    if summary["closed"]:
        raise HTTPException(409, "This day is already closed")
    if summary["unsettled"]:
        raise HTTPException(409, f"{len(summary['unsettled'])} order(s) are not settled. Take payment or void them before closing")
    opening = Decimal(summary["opening_cash"])
    if not summary["opening_known"]:
        if body.opening_cash is None:
            raise HTTPException(422, "Enter the opening cash for this first day")
        opening = money(body.opening_cash)
    expected = money(opening + Decimal(summary["cash_sales"]) + Decimal(summary["petty_in"]) - Decimal(summary["petty_out"]))
    counted = money(body.counted_cash)
    diff = money(counted - expected)
    if diff != 0 and not (body.note or "").strip():
        raise HTTPException(422, "Add a note explaining the cash difference")
    row = DayClose(tenant_id=principal.tenant_id, restaurant_id=outlet_id, business_date=day, opening_cash=opening,
                   cash_sales=Decimal(summary["cash_sales"]), petty_in=Decimal(summary["petty_in"]),
                   petty_out=Decimal(summary["petty_out"]), expected_cash=expected, counted_cash=counted,
                   difference=diff, note=(body.note or "").strip() or None, closed_by=staff_name_of(db, principal))
    db.add(row)
    db.flush()
    audit(db, principal, "day_closed", "day_close", row.id, {"date": day.isoformat(), "difference": str(diff)})
    return _summary(db, principal, outlet, day)


@router.get("/outlets/{outlet_id}/day-closes")
def day_closes(outlet_id: int, db: Session = Depends(get_db),
               principal: Principal = Depends(require_roles(*CASH_ROLES))):
    outlet_or_404(db, principal, outlet_id)
    rows = db.scalars(select(DayClose).where(DayClose.restaurant_id == outlet_id, DayClose.tenant_id == principal.tenant_id)
                      .order_by(DayClose.business_date.desc()).limit(60)).all()
    return [{"date": r.business_date.isoformat(), "opening_cash": str(r.opening_cash), "cash_sales": str(r.cash_sales),
             "petty_in": str(r.petty_in), "petty_out": str(r.petty_out), "expected_cash": str(r.expected_cash),
             "counted_cash": str(r.counted_cash), "difference": str(r.difference), "note": r.note, "closed_by": r.closed_by}
            for r in rows]


def _balances(db: Session, tenant_id: int, ids: list[int]) -> dict[int, Decimal]:
    """Positive = the customer owes the restaurant."""
    rows = db.execute(select(CustomerLedgerEntry.customer_id, CustomerLedgerEntry.kind, func.sum(CustomerLedgerEntry.amount)).where(
        CustomerLedgerEntry.tenant_id == tenant_id, CustomerLedgerEntry.customer_id.in_(ids or [0]),
    ).group_by(CustomerLedgerEntry.customer_id, CustomerLedgerEntry.kind)).all()
    out: dict[int, Decimal] = {}
    for cid, kind, total in rows:
        out[cid] = out.get(cid, Decimal("0")) + (Decimal(total) if kind == "debit" else -Decimal(total))
    return out


def _customer_json(c: Customer, stats: tuple | None = None, balance: Decimal = Decimal("0")) -> dict:
    d = {"id": c.id, "balance_due": str(money(balance)), "name": c.name, "phone": c.phone, "email": c.email, "loyalty_points": c.loyalty_points,
         "birthday": c.birthday, "anniversary": c.anniversary, "gstin": c.gstin, "address": c.address}
    if stats is not None:
        d.update({"orders": stats[0], "spent": str(money(Decimal(stats[1] or 0))), "last_visit": stats[2]})
    return d


@router.get("/outlets/{outlet_id}/customer-book")
def customer_book(outlet_id: int, q: str = "", db: Session = Depends(get_db), principal: Principal = Depends(current_principal)):
    outlet_or_404(db, principal, outlet_id)
    query = select(Customer).where(Customer.tenant_id == principal.tenant_id, Customer.restaurant_id == outlet_id)
    q = q.strip()
    if q:
        like = f"%{q}%"
        query = query.where(Customer.name.ilike(like) | Customer.phone.ilike(like))
    customers = db.scalars(query.order_by(Customer.name).limit(100)).all()
    stats = {r[0]: r[1:] for r in db.execute(select(
        RestaurantOrder.customer_id, func.count(), func.coalesce(func.sum(RestaurantOrder.total), 0), func.max(RestaurantOrder.created_at),
    ).where(RestaurantOrder.tenant_id == principal.tenant_id, RestaurantOrder.restaurant_id == outlet_id,
            RestaurantOrder.customer_id.in_([c.id for c in customers] or [0]), RestaurantOrder.status == "paid",
            ).group_by(RestaurantOrder.customer_id)).all()}
    bal = _balances(db, principal.tenant_id, [c.id for c in customers])
    return [_customer_json(c, stats.get(c.id, (0, 0, None)), bal.get(c.id, Decimal("0"))) for c in customers]


@router.get("/customers/{customer_id}")
def customer_detail(customer_id: int, db: Session = Depends(get_db), principal: Principal = Depends(current_principal)):
    c = db.scalar(select(Customer).where(Customer.id == customer_id, Customer.tenant_id == principal.tenant_id))
    if not c:
        raise HTTPException(404, "Customer not found")
    outlet_or_404(db, principal, c.restaurant_id)
    orders = db.scalars(select(RestaurantOrder).where(
        RestaurantOrder.tenant_id == principal.tenant_id, RestaurantOrder.customer_id == c.id,
    ).order_by(RestaurantOrder.created_at.desc()).limit(30)).all()
    return {**_customer_json(c, None, _balances(db, principal.tenant_id, [c.id]).get(c.id, Decimal("0"))), "orders": [{
        "id": o.id, "order_number": o.order_number, "order_type": o.order_type, "status": o.status,
        "total": str(o.total), "created_at": o.created_at, "items": [f"{i.item_name} x {i.quantity}" for i in o.active_items]}
        for o in orders]}


@router.put("/customers/{customer_id}")
def update_customer(customer_id: int, body: CustomerInput, db: Session = Depends(get_db),
                    principal: Principal = Depends(require_roles(*CASH_ROLES, "waiter", "server"))):
    c = db.scalar(select(Customer).where(Customer.id == customer_id, Customer.tenant_id == principal.tenant_id))
    if not c:
        raise HTTPException(404, "Customer not found")
    outlet_or_404(db, principal, c.restaurant_id)
    for field in ("name", "phone", "email", "birthday", "anniversary", "gstin", "address"):
        setattr(c, field, getattr(body, field))
    audit(db, principal, "customer_updated", "customer", c.id, {})
    return _customer_json(c, None, _balances(db, principal.tenant_id, [c.id]).get(c.id, Decimal("0")))


class LedgerInput(BaseModel):
    kind: Annotated[str, StringConstraints(pattern="^(credit|debit)$")]
    amount: Decimal = Field(gt=0, le=10_000_000, decimal_places=2)
    method: Annotated[str, StringConstraints(pattern="^(cash|upi|card|bank)$")] = "cash"
    remark: str | None = Field(default=None, max_length=200)


def _customer_or_404(db: Session, principal: Principal, customer_id: int) -> Customer:
    c = db.scalar(select(Customer).where(Customer.id == customer_id, Customer.tenant_id == principal.tenant_id))
    if not c:
        raise HTTPException(404, "Customer not found")
    outlet_or_404(db, principal, c.restaurant_id)
    return c


@router.get("/customers/{customer_id}/ledger")
def customer_ledger(customer_id: int, db: Session = Depends(get_db), principal: Principal = Depends(current_principal)):
    c = _customer_or_404(db, principal, customer_id)
    rows = db.scalars(select(CustomerLedgerEntry).where(
        CustomerLedgerEntry.tenant_id == principal.tenant_id, CustomerLedgerEntry.customer_id == c.id,
    ).order_by(CustomerLedgerEntry.id.desc()).limit(100)).all()
    return {"balance_due": str(money(_balances(db, principal.tenant_id, [c.id]).get(c.id, Decimal("0")))),
            "entries": [{"id": r.id, "kind": r.kind, "amount": str(r.amount), "method": r.method, "remark": r.remark,
                         "created_by": r.created_by, "created_at": r.created_at} for r in rows]}


@router.post("/customers/{customer_id}/ledger", status_code=201)
def add_ledger(customer_id: int, body: LedgerInput, db: Session = Depends(get_db),
               principal: Principal = Depends(require_roles(*CASH_ROLES))):
    """A credit is money received from the customer; a debit is a manual charge (for example an old balance)."""
    c = _customer_or_404(db, principal, customer_id)
    entry = CustomerLedgerEntry(tenant_id=principal.tenant_id, restaurant_id=c.restaurant_id, customer_id=c.id,
                                kind=body.kind, amount=money(body.amount), method=body.method if body.kind == "credit" else None,
                                remark=(body.remark or "").strip() or None, created_by=staff_name_of(db, principal))
    db.add(entry)
    db.flush()
    audit(db, principal, "customer_ledger_entry", "customer", c.id, {"kind": body.kind, "amount": str(body.amount)})
    return customer_ledger(customer_id, db, principal)
