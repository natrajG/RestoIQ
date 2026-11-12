from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.service import decode_access_token
from app.db import get_db, set_tenant_context
from app.core.subscriptions import subscription_state
from app.models import OutletMembership, Restaurant, User


@dataclass(frozen=True)
class Principal:
    user_id: int
    tenant_id: int
    role: str
    email: str


def current_principal(request: Request, db: Session = Depends(get_db)) -> Principal:
    token = request.cookies.get("restaurant_session")
    claims = decode_access_token(token) if token else None
    if not claims:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    try:
        user_id, tenant_id = int(claims["sub"]), int(claims["tenant_id"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid session") from None
    set_tenant_context(db, tenant_id)
    user = db.scalar(select(User).where(
        User.id == user_id, User.tenant_id == tenant_id, User.is_active.is_(True),
    ))
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account is inactive or unavailable")
    if user.role != "platform_admin" and not request.url.path.startswith(("/api/v1/auth", "/api/v1/billing")):
        if subscription_state(db, tenant_id)["locked"]:
            raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, "Your free trial has ended. Please contact RestoIQ to activate your plan.")
    return Principal(user.id, user.tenant_id, user.role, user.email)


def require_roles(*roles: str):
    def dependency(principal: Principal = Depends(current_principal)) -> Principal:
        if principal.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient role")
        return principal

    return dependency


def has_outlet_access(db: Session, principal: Principal, outlet_id: int) -> bool:
    if principal.role in {"owner", "admin", "platform_admin"}:
        return True
    return db.scalar(
        select(OutletMembership.id).where(
            OutletMembership.tenant_id == principal.tenant_id,
            OutletMembership.outlet_id == outlet_id,
            OutletMembership.user_id == principal.user_id,
        )
    ) is not None


def require_outlet_access(db: Session, principal: Principal, outlet_id: int) -> Restaurant:
    outlet = db.scalar(select(Restaurant).where(
        Restaurant.id == outlet_id,
        Restaurant.tenant_id == principal.tenant_id,
    ))
    if not outlet or not has_outlet_access(db, principal, outlet_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Outlet not found")
    return outlet
