import re

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth.dependencies import Principal, require_roles
from app.auth.repository import user_by_email
from app.auth.service import hash_password
from app.db import get_db, set_tenant_context
from app.models import OutletMembership, Restaurant, User

router = APIRouter(prefix="/api/v1/staff", tags=["staff"])
ADMINS = ("owner", "admin")
MANAGERS = ("owner", "admin", "manager")
STAFF_ROLES = ("manager", "cashier", "waiter", "kitchen", "cleaner", "analyst")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")


class StaffCreate(BaseModel):
    email: str = Field(max_length=254)
    full_name: str | None = Field(default=None, max_length=120)
    role: str
    password: str = Field(min_length=8, max_length=128)
    outlet_ids: list[int] = Field(min_length=1)

    @field_validator("email")
    @classmethod
    def valid_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not EMAIL_RE.match(v):
            raise ValueError("Enter a valid email address")
        return v


class StaffUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=120)
    role: str | None = None
    is_active: bool | None = None
    outlet_ids: list[int] | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


def _assignable(principal: Principal) -> tuple[str, ...]:
    return STAFF_ROLES if principal.role in ADMINS else tuple(r for r in STAFF_ROLES if r != "manager")


def _check_role(principal: Principal, role: str) -> None:
    if role not in _assignable(principal):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot assign this role")


def _check_outlets(db: Session, principal: Principal, outlet_ids: list[int]) -> list[int]:
    ids = sorted(set(outlet_ids))
    found = set(db.scalars(select(Restaurant.id).where(
        Restaurant.tenant_id == principal.tenant_id, Restaurant.id.in_(ids))))
    if found != set(ids):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown outlet selected")
    return ids


def _serialize(db: Session, user: User) -> dict:
    outlets = list(db.scalars(select(OutletMembership.outlet_id).where(OutletMembership.user_id == user.id)))
    return {"id": user.id, "email": user.email, "full_name": user.full_name, "role": user.role,
            "is_active": user.is_active, "outlet_ids": outlets}


def _set_memberships(db: Session, user: User, role: str, outlet_ids: list[int]) -> None:
    db.execute(delete(OutletMembership).where(OutletMembership.user_id == user.id))
    for oid in outlet_ids:
        db.add(OutletMembership(tenant_id=user.tenant_id, outlet_id=oid, user_id=user.id, role=role))


def _target(db: Session, principal: Principal, user_id: int) -> User:
    user = db.scalar(select(User).where(User.id == user_id, User.tenant_id == principal.tenant_id))
    if not user or user.role not in STAFF_ROLES:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Staff member not found")
    if user.role == "manager" and principal.role not in ADMINS:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the owner can change managers")
    return user


@router.get("")
def list_staff(principal: Principal = Depends(require_roles(*MANAGERS)), db: Session = Depends(get_db)):
    set_tenant_context(db, principal.tenant_id)
    users = db.scalars(select(User).where(
        User.tenant_id == principal.tenant_id, User.role.in_(STAFF_ROLES)).order_by(User.id))
    return {"staff": [_serialize(db, u) for u in users], "assignable_roles": _assignable(principal)}


@router.post("", status_code=201)
def create_staff(payload: StaffCreate, principal: Principal = Depends(require_roles(*MANAGERS)),
                 db: Session = Depends(get_db)):
    set_tenant_context(db, principal.tenant_id)
    _check_role(principal, payload.role)
    ids = _check_outlets(db, principal, payload.outlet_ids)
    if user_by_email(db, payload.email):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    user = User(tenant_id=principal.tenant_id, email=payload.email, role=payload.role, full_name=(payload.full_name or None),
                password_hash=hash_password(payload.password), is_active=True)
    db.add(user)
    db.flush()
    _set_memberships(db, user, payload.role, ids)
    db.commit()
    set_tenant_context(db, principal.tenant_id)
    return _serialize(db, user)


@router.patch("/{user_id}")
def update_staff(user_id: int, payload: StaffUpdate,
                 principal: Principal = Depends(require_roles(*MANAGERS)), db: Session = Depends(get_db)):
    set_tenant_context(db, principal.tenant_id)
    user = _target(db, principal, user_id)
    if payload.role is not None:
        _check_role(principal, payload.role)
        user.role = payload.role
    if payload.full_name is not None:
        user.full_name = payload.full_name.strip() or None
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.password:
        user.password_hash = hash_password(payload.password)
    if payload.outlet_ids is not None or payload.role is not None:
        current = payload.outlet_ids if payload.outlet_ids is not None else list(db.scalars(
            select(OutletMembership.outlet_id).where(OutletMembership.user_id == user.id)))
        _set_memberships(db, user, user.role, _check_outlets(db, principal, current) if current else [])
    db.commit()
    set_tenant_context(db, principal.tenant_id)
    return _serialize(db, user)
