import csv
import io
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import Principal, require_roles
from app.core.audit import audit
from app.db import get_db
from app.integrations import providers as _providers  # noqa: F401
from app.integrations.service import publish_event
from app.models import MenuCategory, MenuItem, MenuOption, OrderItem, Payment, Restaurant, RestaurantOrder, TenantProfile
from app.pos.service import money, order_charges, order_or_404, outlet_or_404

router = APIRouter(prefix="/api/v1", tags=["menu"])
MANAGERS = ("owner", "manager", "admin")
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class CategoryInput(BaseModel):
    name: Name
    sort_order: int = Field(default=0, ge=0, le=1000)


class CategoryPatch(BaseModel):
    name: Name | None = None
    sort_order: int | None = Field(default=None, ge=0, le=1000)


class ItemPatch(BaseModel):
    name: Name | None = None
    category_id: int | None = None
    price: Decimal | None = Field(default=None, ge=0, le=1000000, decimal_places=2)
    cost_price: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    tax_rate: Decimal | None = Field(default=None, ge=0, le=100, decimal_places=3)
    active: bool | None = None


def _category(db: Session, tenant_id: int, outlet_id: int, category_id: int) -> MenuCategory:
    cat = db.scalar(select(MenuCategory).where(
        MenuCategory.id == category_id, MenuCategory.restaurant_id == outlet_id, MenuCategory.tenant_id == tenant_id))
    if not cat:
        raise HTTPException(404, "Menu category not found")
    return cat


@router.post("/outlets/{outlet_id}/menu/categories", status_code=201)
def create_category(outlet_id: int, body: CategoryInput, db: Session = Depends(get_db),
                    principal: Principal = Depends(require_roles(*MANAGERS))):
    outlet_or_404(db, principal, outlet_id)
    if db.scalar(select(MenuCategory.id).where(
            MenuCategory.restaurant_id == outlet_id, MenuCategory.tenant_id == principal.tenant_id,
            func.lower(MenuCategory.name) == body.name.lower())):
        raise HTTPException(409, "A category with this name already exists")
    cat = MenuCategory(tenant_id=principal.tenant_id, restaurant_id=outlet_id, name=body.name, sort_order=body.sort_order)
    db.add(cat)
    db.flush()
    audit(db, principal, "menu_category_created", "menu_category", cat.id)
    return {"id": cat.id, "name": cat.name, "sort_order": cat.sort_order}


@router.patch("/outlets/{outlet_id}/menu/categories/{category_id}")
def update_category(outlet_id: int, category_id: int, body: CategoryPatch, db: Session = Depends(get_db),
                    principal: Principal = Depends(require_roles(*MANAGERS))):
    outlet_or_404(db, principal, outlet_id)
    cat = _category(db, principal.tenant_id, outlet_id, category_id)
    if body.name is not None:
        cat.name = body.name
    if body.sort_order is not None:
        cat.sort_order = body.sort_order
    audit(db, principal, "menu_category_updated", "menu_category", cat.id)
    return {"id": cat.id, "name": cat.name, "sort_order": cat.sort_order}


@router.delete("/outlets/{outlet_id}/menu/categories/{category_id}", status_code=204)
def delete_category(outlet_id: int, category_id: int, db: Session = Depends(get_db),
                    principal: Principal = Depends(require_roles(*MANAGERS))):
    outlet_or_404(db, principal, outlet_id)
    cat = _category(db, principal.tenant_id, outlet_id, category_id)
    for item in db.scalars(select(MenuItem).where(MenuItem.category_id == cat.id, MenuItem.tenant_id == principal.tenant_id)):
        item.category_id = None
    db.delete(cat)
    audit(db, principal, "menu_category_deleted", "menu_category", category_id)


@router.patch("/outlets/{outlet_id}/menu/items/{item_id}")
def update_item(outlet_id: int, item_id: int, body: ItemPatch, db: Session = Depends(get_db),
                principal: Principal = Depends(require_roles(*MANAGERS))):
    """Price/GST changes apply to new orders only; past orders keep the price and tax they were billed at."""
    outlet_or_404(db, principal, outlet_id)
    item = db.scalar(select(MenuItem).where(
        MenuItem.id == item_id, MenuItem.restaurant_id == outlet_id, MenuItem.tenant_id == principal.tenant_id))
    if not item:
        raise HTTPException(404, "Menu item not found")
    data = body.model_dump(exclude_unset=True)
    if "category_id" in data and data["category_id"] is not None:
        _category(db, principal.tenant_id, outlet_id, data["category_id"])
    for key in ("name", "category_id", "price", "cost_price", "tax_rate", "active"):
        if key in data and (data[key] is not None or key in ("category_id", "cost_price")):
            setattr(item, key, data[key])
    audit(db, principal, "menu_item_updated", "menu_item", item.id, {k: str(v) for k, v in data.items()})
    if "price" in data or "name" in data:
        publish_event(db, principal.tenant_id, outlet_id, "menu.item.updated",
                      {"item_id": item.id, "name": item.name, "price": str(item.price)})
    if "active" in data:
        publish_event(db, principal.tenant_id, outlet_id, "item.availability.changed",
                      {"item_id": item.id, "available": item.active})
    return {"id": item.id, "name": item.name, "price": str(item.price), "tax_rate": str(item.tax_rate), "active": item.active}


@router.delete("/outlets/{outlet_id}/menu/items/{item_id}", status_code=204)
def delete_item(outlet_id: int, item_id: int, db: Session = Depends(get_db),
                principal: Principal = Depends(require_roles(*MANAGERS))):
    """Only items never sold can be removed; sold items must be switched off so old bills stay intact."""
    outlet_or_404(db, principal, outlet_id)
    item = db.scalar(select(MenuItem).where(
        MenuItem.id == item_id, MenuItem.restaurant_id == outlet_id, MenuItem.tenant_id == principal.tenant_id))
    if not item:
        raise HTTPException(404, "Menu item not found")
    if db.scalar(select(OrderItem.id).where(OrderItem.menu_item_id == item.id).limit(1)):
        raise HTTPException(409, "This item has been sold. Switch it off under Available instead.")
    for opt in db.scalars(select(MenuOption).where(MenuOption.menu_item_id == item.id)):
        db.delete(opt)
    db.delete(item)
    audit(db, principal, "menu_item_deleted", "menu_item", item_id)


class GstSettings(BaseModel):
    gst_scheme: str = Field(pattern="^(regular|composition)$")


@router.get("/outlets/{outlet_id}/gst-settings")
def get_gst(outlet_id: int, db: Session = Depends(get_db), principal: Principal = Depends(require_roles(*MANAGERS))):
    outlet = outlet_or_404(db, principal, outlet_id)
    return {"gst_scheme": (outlet.tax_config or {}).get("gst_scheme", "regular")}


@router.put("/outlets/{outlet_id}/gst-settings")
def set_gst(outlet_id: int, body: GstSettings, db: Session = Depends(get_db),
            principal: Principal = Depends(require_roles(*MANAGERS))):
    """Composition dealers must not charge GST on bills; new orders then carry 0% tax."""
    outlet = outlet_or_404(db, principal, outlet_id)
    outlet.tax_config = {**(outlet.tax_config or {}), "gst_scheme": body.gst_scheme}
    audit(db, principal, "gst_scheme_changed", "outlet", outlet_id, {"gst_scheme": body.gst_scheme})
    return {"gst_scheme": body.gst_scheme}


class BillingSettings(BaseModel):
    service_charge_pct: Decimal = Field(ge=0, le=20, decimal_places=2)
    round_off: bool
    upi_id: str | None = Field(default=None, max_length=80, pattern=r"^$|^[A-Za-z0-9._-]{2,64}@[A-Za-z][A-Za-z0-9.-]{1,30}$")


@router.get("/outlets/{outlet_id}/billing-settings")
def get_billing(outlet_id: int, db: Session = Depends(get_db), principal: Principal = Depends(require_roles(*MANAGERS))):
    cfg = outlet_or_404(db, principal, outlet_id).tax_config or {}
    return {"service_charge_pct": str(cfg.get("service_charge_pct", 0)), "round_off": bool(cfg.get("round_off", False)),
            "upi_id": cfg.get("upi_id", "")}


@router.put("/outlets/{outlet_id}/billing-settings")
def set_billing(outlet_id: int, body: BillingSettings, db: Session = Depends(get_db),
                principal: Principal = Depends(require_roles(*MANAGERS))):
    """Service charge percent and rupee round-off. They apply to bills recalculated or created from now on."""
    outlet = outlet_or_404(db, principal, outlet_id)
    outlet.tax_config = {**(outlet.tax_config or {}), "service_charge_pct": str(body.service_charge_pct), "round_off": body.round_off}
    if "upi_id" in body.model_fields_set:  # omitted by older clients: leave the saved UPI ID alone
        outlet.tax_config = {**outlet.tax_config, "upi_id": (body.upi_id or "").strip()}
    audit(db, principal, "billing_settings_changed", "outlet", outlet_id, {"service_charge_pct": str(body.service_charge_pct), "round_off": body.round_off})
    return {"service_charge_pct": str(body.service_charge_pct), "round_off": body.round_off}


class OptionInput(BaseModel):
    kind: Literal["variant", "addon"]
    name: Name
    price: Decimal = Field(ge=0, le=1000000, decimal_places=2)


def _item(db: Session, tenant_id: int, outlet_id: int, item_id: int) -> MenuItem:
    item = db.scalar(select(MenuItem).where(
        MenuItem.id == item_id, MenuItem.restaurant_id == outlet_id, MenuItem.tenant_id == tenant_id))
    if not item:
        raise HTTPException(404, "Menu item not found")
    return item


@router.post("/outlets/{outlet_id}/menu/items/{item_id}/options", status_code=201)
def add_option(outlet_id: int, item_id: int, body: OptionInput, db: Session = Depends(get_db),
               principal: Principal = Depends(require_roles(*MANAGERS))):
    outlet_or_404(db, principal, outlet_id)
    item = _item(db, principal.tenant_id, outlet_id, item_id)
    if db.scalar(select(MenuOption.id).where(
            MenuOption.menu_item_id == item.id, MenuOption.tenant_id == principal.tenant_id,
            MenuOption.kind == body.kind, MenuOption.active.is_(True), func.lower(MenuOption.name) == body.name.lower())):
        raise HTTPException(409, "This option already exists")
    opt = MenuOption(tenant_id=principal.tenant_id, menu_item_id=item.id, kind=body.kind, name=body.name, price=body.price)
    db.add(opt)
    db.flush()
    audit(db, principal, "menu_option_added", "menu_item", item.id)
    db.commit()
    return {"id": opt.id, "kind": opt.kind, "name": opt.name, "price": str(opt.price)}


@router.delete("/outlets/{outlet_id}/menu/items/{item_id}/options/{option_id}", status_code=204)
def remove_option(outlet_id: int, item_id: int, option_id: int, db: Session = Depends(get_db),
                  principal: Principal = Depends(require_roles(*MANAGERS))):
    outlet_or_404(db, principal, outlet_id)
    _item(db, principal.tenant_id, outlet_id, item_id)
    opt = db.scalar(select(MenuOption).where(
        MenuOption.id == option_id, MenuOption.menu_item_id == item_id, MenuOption.tenant_id == principal.tenant_id))
    if not opt:
        raise HTTPException(404, "Option not found")
    opt.active = False  # past orders keep their snapshot
    audit(db, principal, "menu_option_removed", "menu_item", item_id)
    db.commit()


@router.get("/orders/{order_id}/bill")
def bill(order_id: int, db: Session = Depends(get_db),
         principal: Principal = Depends(require_roles(*MANAGERS, "cashier", "waiter", "server"))):
    """Tax invoice data. Restaurant dine-in is intra-state, so each GST rate splits equally into CGST and SGST."""
    order = order_or_404(db, principal, order_id)
    profile = db.scalar(select(TenantProfile).where(TenantProfile.tenant_id == principal.tenant_id))
    outlet = db.get(Restaurant, order.restaurant_id)
    paid = db.scalars(select(Payment).where(Payment.order_id == order.id, Payment.tenant_id == principal.tenant_id))
    composition = bool(outlet and (outlet.tax_config or {}).get("gst_scheme") == "composition")
    lines = [{"name": i.item_name, "addons": [a["name"] for a in (i.addons or [])], "quantity": i.quantity, "unit_price": str(i.unit_price),
              "amount": "0.00" if i.complimentary else str(money(Decimal(i.quantity) * i.unit_price)), "complimentary": i.complimentary, "gst_rate": str(i.tax_rate)} for i in order.active_items]
    gst = []
    for rate, taxable, tax in ([] if composition else order_charges(order, outlet)["slabs"]):
        half = money(tax / 2)
        gst.append({"rate": str(rate), "taxable": str(taxable), "cgst": str(half), "sgst": str(tax - half), "total_tax": str(tax)})
    return {
        "restaurant": outlet.name if outlet else "", "legal_gstin": profile.gstin if profile else None,
        "address": f"{profile.address_line}, {profile.city} {profile.pincode}" if profile else None,
        "order_number": order.order_number, "date": order.created_at, "status": order.status,
        "order_type": order.order_type, "contact_name": order.contact_name, "contact_phone": order.contact_phone,
        "delivery_address": order.delivery_address,
        "lines": lines, "subtotal": str(order.subtotal), "gst": gst, "tax_total": str(order.tax_total),
        "discount": str(order.discount_total), "discount_reason": order.discount_reason,
        "service_charge": str(order.service_charge), "round_off": str(order.round_off), "total": str(order.total),
        "tip": str(order.tip), "payable": str(money(order.total + order.tip)),
        "payments": [{"method": p.method, "amount": str(p.amount)} for p in paid],
        "tax_invoice": bool(profile and profile.gstin) and not composition,
        "notice": "Composition taxable person, not eligible to collect tax on supplies" if composition else None,
        "place_of_supply": outlet.state_code if outlet else None,
        "upi_id": (outlet.tax_config or {}).get("upi_id") or None if outlet else None,
    }


@router.get("/outlets/{outlet_id}/reports/gst")
def gst_report(
    outlet_id: int, start: date = Query(alias="from"), end: date = Query(alias="to"), format: str = "json",
    db: Session = Depends(get_db), principal: Principal = Depends(require_roles(*MANAGERS, "analyst", "cashier")),
):
    """Sales by day and GST rate for filing. Counts bills that are paid or completed; cancelled/refunded bills are excluded."""
    outlet = outlet_or_404(db, principal, outlet_id)
    if end < start or (end - start).days > 366:
        raise HTTPException(422, "Choose a range of at most one year, with 'from' on or before 'to'")
    tz = ZoneInfo(outlet.timezone)
    lo = datetime.combine(start, time.min, tz)
    hi = datetime.combine(end + timedelta(days=1), time.min, tz)
    orders = db.scalars(select(RestaurantOrder).where(
        RestaurantOrder.tenant_id == principal.tenant_id, RestaurantOrder.restaurant_id == outlet_id,
        RestaurantOrder.status.in_(["paid", "completed"]), RestaurantOrder.created_at >= lo, RestaurantOrder.created_at < hi,
    ).order_by(RestaurantOrder.created_at))
    rows: dict[tuple[str, Decimal], list[Decimal]] = defaultdict(lambda: [Decimal("0"), Decimal("0")])
    days: dict[str, dict] = defaultdict(lambda: {"bills": 0, "discount": Decimal("0"), "total": Decimal("0")})
    first: dict[str, str] = {}
    last: dict[str, str] = {}
    for o in orders:
        d = o.created_at.astimezone(tz).date().isoformat()
        days[d]["bills"] += 1
        days[d]["discount"] += o.discount_total
        days[d]["total"] += o.total
        first.setdefault(d, o.order_number)
        last[d] = o.order_number
        for rate, taxable, tax in order_charges(o, outlet)["slabs"]:
            r = rows[(d, rate)]
            r[0] += taxable
            r[1] += tax
    lines = []
    for (d, rate), (taxable, tax) in sorted(rows.items()):
        half = money(tax / 2)
        lines.append({"date": d, "gst_rate": str(rate), "taxable": str(taxable), "cgst": str(half), "sgst": str(tax - half), "tax": str(tax)})
    daily = [{"date": d, "bills": v["bills"], "first_bill": first[d], "last_bill": last[d], "discount": str(v["discount"]), "total": str(v["total"])} for d, v in sorted(days.items())]
    totals = {
        "taxable": str(sum((Decimal(x["taxable"]) for x in lines), Decimal("0"))),
        "cgst": str(sum((Decimal(x["cgst"]) for x in lines), Decimal("0"))),
        "sgst": str(sum((Decimal(x["sgst"]) for x in lines), Decimal("0"))),
        "bills": sum(v["bills"] for v in days.values()), "total": str(sum((v["total"] for v in days.values()), Decimal("0"))),
    }
    if format == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["date", "gst_rate_percent", "taxable_value", "cgst", "sgst", "total_tax"])
        for x in lines:
            w.writerow([x["date"], x["gst_rate"], x["taxable"], x["cgst"], x["sgst"], x["tax"]])
        w.writerow(["TOTAL", "", totals["taxable"], totals["cgst"], totals["sgst"], ""])
        return Response(buf.getvalue(), media_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="gst-{start}-{end}.csv"'})
    return {"from": start.isoformat(), "to": end.isoformat(), "lines": lines, "daily": daily, "totals": totals,
            "composition": (outlet.tax_config or {}).get("gst_scheme") == "composition",
            "note": "Partial refunds are not netted. Have your accountant verify before filing."}
