"""Bulk menu import from CSV or Excel: a preview first, then a confirmed save with no partial imports."""
import csv
import io
import re
from decimal import Decimal, InvalidOperation

from starlette.concurrency import run_in_threadpool
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import Principal, require_roles
from app.core.audit import audit
from app.db import get_db
from app.models import MenuCategory, MenuItem, MenuOption
from app.pos.service import outlet_or_404

router = APIRouter(prefix="/api/v1", tags=["menu"])
MANAGERS = ("owner", "manager", "admin")
MAX_BYTES = 2_000_000
MAX_ROWS = 1000
GST_RATES = {Decimal(v) for v in (0, 5, 12, 18, 28)}
ALIASES = {
    "category": "category", "name": "name", "item": "name", "item name": "name",
    "code": "code", "sku": "code", "item code": "code",
    "price": "price", "rate": "price", "gst": "gst", "gst %": "gst", "tax": "gst",
    "sizes": "sizes", "size": "sizes", "addons": "addons", "add-ons": "addons", "add ons": "addons",
}
TEMPLATE = (
    "category,name,code,price,gst,sizes,addons\n"
    "Starters,Paneer Tikka,PT01,220,5,Half=120;Full=220,Extra mint chutney=10\n"
    "Main Course,Veg Biryani,VB01,180,5,,Raita=30\n"
    "Beverages,Masala Chai,CH01,20,5,,\n"
)


def _rows(raw: bytes, filename: str) -> list[list[str]]:
    if filename.lower().endswith((".xlsx", ".xlsm")):
        from openpyxl import load_workbook
        try:
            sheet = load_workbook(io.BytesIO(raw), read_only=True, data_only=True).active
            return [["" if c is None else str(c).strip() for c in row] for row in sheet.iter_rows(values_only=True)]
        except Exception as exc:
            raise HTTPException(422, "Could not read this Excel file. Save it as .xlsx or .csv and try again.") from exc
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise HTTPException(422, "Could not read this file. Save it as CSV (UTF-8) and try again.")
    return [[c.strip() for c in row] for row in csv.reader(io.StringIO(text))]


def _money(value: str) -> Decimal:
    return Decimal(re.sub(r"[₹,\s]|rs\.?", "", value.lower())).quantize(Decimal("0.01"))


def _options(text: str, label: str) -> list[tuple[str, Decimal]]:
    out = []
    for part in re.split(r"[;|]", text):
        if not part.strip():
            continue
        name, sep, price = part.rpartition("=")
        if not sep or not name.strip() or len(name.strip()) > 80:
            raise ValueError(f"{label} must look like Half=120;Full=200")
        amount = _money(price)
        if amount < 0:
            raise ValueError(f"{label} price cannot be negative")
        out.append((name.strip(), amount))
    return out


def parse_menu(raw: bytes, filename: str) -> list[dict]:
    if len(raw) > MAX_BYTES:
        raise HTTPException(413, "File is too large (limit 2 MB)")
    table = [r for r in _rows(raw, filename) if any(c for c in r)]
    if not table:
        raise HTTPException(422, "The file is empty")
    columns = {i: ALIASES[h.lower().strip()] for i, h in enumerate(table[0]) if h.lower().strip() in ALIASES}
    missing = {"name", "price"} - set(columns.values())
    if missing:
        raise HTTPException(422, f"Missing column(s): {', '.join(sorted(missing))}. Download the template to see the format.")
    if len(table) - 1 > MAX_ROWS:
        raise HTTPException(413, f"Too many rows (limit {MAX_ROWS})")
    items, seen = [], set()
    for number, row in enumerate(table[1:], start=2):
        cells = {columns[i]: (row[i] if i < len(row) else "") for i in columns}
        entry = {"row": number, "category": cells.get("category", "").strip(), "name": cells.get("name", "").strip(),
                 "code": cells.get("code", "").strip(), "error": None}
        try:
            if not entry["name"] or len(entry["name"]) > 120:
                raise ValueError("Item name is required (max 120 characters)")
            if len(entry["code"]) > 64 or len(entry["category"]) > 120:
                raise ValueError("Code or category is too long")
            try:
                entry["price"] = _money(cells.get("price", ""))
            except (InvalidOperation, ValueError):
                raise ValueError("Price must be a number") from None
            if not 0 <= entry["price"] <= 1_000_000:
                raise ValueError("Price is out of range")
            gst = cells.get("gst", "").replace("%", "").strip()
            try:
                entry["gst"] = Decimal(gst) if gst else Decimal(5)
            except InvalidOperation:
                raise ValueError("GST must be 0, 5, 12, 18 or 28") from None
            if entry["gst"] not in GST_RATES:
                raise ValueError("GST must be 0, 5, 12, 18 or 28")
            entry["sizes"] = _options(cells.get("sizes", ""), "Sizes")
            entry["addons"] = _options(cells.get("addons", ""), "Add-ons")
            key = (entry["code"] or entry["name"]).lower()
            if key in seen:
                raise ValueError("Duplicate of an earlier row in this file")
            seen.add(key)
        except ValueError as exc:
            entry["error"] = str(exc)
        items.append(entry)
    return items


def _apply(db: Session, principal: Principal, outlet_id: int, parsed: list[dict], commit: bool) -> dict:
    tenant = principal.tenant_id
    existing = list(db.scalars(select(MenuItem).where(MenuItem.restaurant_id == outlet_id, MenuItem.tenant_id == tenant)))
    by_code = {i.sku.lower(): i for i in existing}
    by_name = {i.name.lower(): i for i in existing}
    categories = {c.name.lower(): c for c in db.scalars(select(MenuCategory).where(
        MenuCategory.restaurant_id == outlet_id, MenuCategory.tenant_id == tenant))}
    used_codes, counter = set(by_code), len(existing)
    report = {"created": 0, "updated": 0, "errors": 0, "rows": []}
    for e in parsed:
        row = {"row": e["row"], "name": e["name"], "category": e["category"], "code": e["code"],
               "price": str(e.get("price", "")), "gst": str(e.get("gst", "")), "status": "error", "message": e["error"]}
        if e["error"]:
            report["errors"] += 1
            report["rows"].append(row)
            continue
        item = (by_code.get(e["code"].lower()) if e["code"] else None) or by_name.get(e["name"].lower())
        row["status"] = "update" if item else "new"
        report["updated" if item else "created"] += 1
        if not item and not e["code"]:
            while True:
                counter += 1
                code = f"M{counter:03d}"
                if code.lower() not in used_codes:
                    break
            e["code"] = row["code"] = code
        if e["code"]:
            used_codes.add(e["code"].lower())
        report["rows"].append(row)
        e["_item"] = item
    if not commit or report["errors"]:
        return report
    for e in parsed:
        category = None
        if e["category"]:
            category = categories.get(e["category"].lower())
            if not category:
                category = MenuCategory(tenant_id=tenant, restaurant_id=outlet_id, name=e["category"])
                db.add(category)
                db.flush()
                categories[e["category"].lower()] = category
        item = e["_item"]
        if item:
            item.name, item.price, item.tax_rate, item.active = e["name"], e["price"], e["gst"], True
            if category:
                item.category_id = category.id
        else:
            item = MenuItem(tenant_id=tenant, restaurant_id=outlet_id, category_id=category.id if category else None,
                            name=e["name"], sku=e["code"], price=e["price"], tax_rate=e["gst"])
            db.add(item)
            db.flush()
        for kind, values in (("variant", e["sizes"]), ("addon", e["addons"])):
            for name, price in values:
                opt = db.scalar(select(MenuOption).where(
                    MenuOption.menu_item_id == item.id, MenuOption.tenant_id == tenant, MenuOption.kind == kind,
                    MenuOption.active.is_(True), func.lower(MenuOption.name) == name.lower()))
                if opt:
                    opt.price = price
                else:
                    db.add(MenuOption(tenant_id=tenant, menu_item_id=item.id, kind=kind, name=name, price=price))
    audit(db, principal, "menu_imported", "menu", outlet_id, {"created": report["created"], "updated": report["updated"]})
    db.commit()
    report["saved"] = True
    return report


@router.get("/outlets/{outlet_id}/menu/import-template")
def import_template(outlet_id: int, db: Session = Depends(get_db), principal: Principal = Depends(require_roles(*MANAGERS))):
    outlet_or_404(db, principal, outlet_id)
    return Response(TEMPLATE, media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="restoiq-menu-template.csv"'})


@router.post("/outlets/{outlet_id}/menu/import")
async def import_menu(outlet_id: int, file: UploadFile = File(...), commit: bool = False, db: Session = Depends(get_db),
                      principal: Principal = Depends(require_roles(*MANAGERS))):
    outlet_or_404(db, principal, outlet_id)
    raw = await file.read(MAX_BYTES + 1)
    report = await run_in_threadpool(_apply, db, principal, outlet_id, parse_menu(raw, file.filename or ""), commit)
    if commit and report["errors"]:
        raise HTTPException(422, "Fix the rows with errors and upload again. Nothing was saved.")
    return report
