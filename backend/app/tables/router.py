from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import Principal, require_outlet_access, require_roles
from app.core.audit import audit
from app.db import get_db, set_tenant_context
from app.models import DiningTable, Floor

router = APIRouter(prefix="/api/v1/outlets/{outlet_id}", tags=["tables"])
MANAGERS = ("owner", "admin", "manager")
MAX_TABLES = 200


class TableCreate(BaseModel):
    name: str = Field(min_length=1, max_length=48)
    seats: int = Field(default=4, ge=1, le=50)
    floor_name: str | None = Field(default=None, max_length=120)


class TableBulkCreate(BaseModel):
    prefix: str = Field(default="T", max_length=8)
    count: int = Field(ge=1, le=100)
    seats: int = Field(default=4, ge=1, le=50)
    floor_name: str | None = Field(default=None, max_length=120)


class TableUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=48)
    seats: int | None = Field(default=None, ge=1, le=50)


def _floor(db: Session, principal: Principal, outlet_id: int, name: str | None) -> Floor:
    name = (name or "Main Floor").strip() or "Main Floor"
    floor = db.scalar(select(Floor).where(Floor.restaurant_id == outlet_id, Floor.tenant_id == principal.tenant_id, Floor.name == name))
    if not floor:
        floor = Floor(tenant_id=principal.tenant_id, restaurant_id=outlet_id, name=name)
        db.add(floor)
        db.flush()
    return floor


def _json(t: DiningTable, floors: dict[int, str]) -> dict:
    return {"id": t.id, "name": t.name, "seats": t.seats, "status": t.status,
            "floor_id": t.floor_id, "floor_name": floors.get(t.floor_id or 0)}


def _all(db: Session, principal: Principal, outlet_id: int) -> list[DiningTable]:
    return list(db.scalars(select(DiningTable).where(
        DiningTable.restaurant_id == outlet_id, DiningTable.tenant_id == principal.tenant_id).order_by(DiningTable.id)))


def _count(db: Session, principal: Principal, outlet_id: int) -> int:
    return len(_all(db, principal, outlet_id))


@router.get("/tables-admin")
def list_tables_admin(outlet_id: int, principal: Principal = Depends(require_roles(*MANAGERS)), db: Session = Depends(get_db)):
    set_tenant_context(db, principal.tenant_id)
    require_outlet_access(db, principal, outlet_id)
    floors = {f.id: f.name for f in db.scalars(select(Floor).where(Floor.restaurant_id == outlet_id))}
    return {"tables": [_json(t, floors) for t in _all(db, principal, outlet_id)]}


@router.post("/tables", status_code=201)
def create_table(outlet_id: int, body: TableCreate, principal: Principal = Depends(require_roles(*MANAGERS)),
                 db: Session = Depends(get_db)):
    set_tenant_context(db, principal.tenant_id)
    require_outlet_access(db, principal, outlet_id)
    if _count(db, principal, outlet_id) >= MAX_TABLES:
        raise HTTPException(409, f"An outlet can have at most {MAX_TABLES} tables")
    name = body.name.strip()
    if db.scalar(select(DiningTable.id).where(DiningTable.restaurant_id == outlet_id, DiningTable.name == name)):
        raise HTTPException(409, f"Table {name} already exists")
    floor = _floor(db, principal, outlet_id, body.floor_name)
    table = DiningTable(tenant_id=principal.tenant_id, restaurant_id=outlet_id, floor_id=floor.id,
                        name=name, seats=body.seats, status="FREE")
    db.add(table)
    db.flush()
    audit(db, principal, "table_created", "table", table.id, {"name": name})
    return _json(table, {floor.id: floor.name})


@router.post("/tables/bulk", status_code=201)
def create_tables_bulk(outlet_id: int, body: TableBulkCreate, principal: Principal = Depends(require_roles(*MANAGERS)),
                       db: Session = Depends(get_db)):
    set_tenant_context(db, principal.tenant_id)
    require_outlet_access(db, principal, outlet_id)
    existing = {t.name for t in _all(db, principal, outlet_id)}
    if len(existing) + body.count > MAX_TABLES:
        raise HTTPException(409, f"An outlet can have at most {MAX_TABLES} tables")
    floor = _floor(db, principal, outlet_id, body.floor_name)
    created, n = [], 0
    while len(created) < body.count:
        n += 1
        name = f"{body.prefix.strip()}{n:02}"
        if name in existing:
            continue
        created.append(DiningTable(tenant_id=principal.tenant_id, restaurant_id=outlet_id, floor_id=floor.id,
                                   name=name, seats=body.seats, status="FREE"))
    db.add_all(created)
    db.flush()
    audit(db, principal, "tables_bulk_created", "outlet", outlet_id, {"count": body.count})
    return {"created": [_json(t, {floor.id: floor.name}) for t in created]}


def _get(db: Session, principal: Principal, outlet_id: int, table_id: int) -> DiningTable:
    table = db.scalar(select(DiningTable).where(DiningTable.id == table_id, DiningTable.restaurant_id == outlet_id,
                                                DiningTable.tenant_id == principal.tenant_id))
    if not table:
        raise HTTPException(404, "Table not found")
    return table


@router.patch("/tables/{table_id}")
def update_table(outlet_id: int, table_id: int, body: TableUpdate, principal: Principal = Depends(require_roles(*MANAGERS)),
                 db: Session = Depends(get_db)):
    set_tenant_context(db, principal.tenant_id)
    require_outlet_access(db, principal, outlet_id)
    table = _get(db, principal, outlet_id, table_id)
    if body.name is not None and body.name.strip() != table.name:
        name = body.name.strip()
        if db.scalar(select(DiningTable.id).where(DiningTable.restaurant_id == outlet_id, DiningTable.name == name)):
            raise HTTPException(409, f"Table {name} already exists")
        table.name = name
    if body.seats is not None:
        table.seats = body.seats
    floors = {f.id: f.name for f in db.scalars(select(Floor).where(Floor.restaurant_id == outlet_id))}
    return _json(table, floors)


@router.delete("/tables/{table_id}", status_code=204)
def delete_table(outlet_id: int, table_id: int, principal: Principal = Depends(require_roles(*MANAGERS)),
                 db: Session = Depends(get_db)):
    set_tenant_context(db, principal.tenant_id)
    require_outlet_access(db, principal, outlet_id)
    table = _get(db, principal, outlet_id, table_id)
    audit(db, principal, "table_deleted", "table", table.id, {"name": table.name})
    try:
        db.delete(table)
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "This table has orders, tasks or camera history and cannot be deleted") from None
