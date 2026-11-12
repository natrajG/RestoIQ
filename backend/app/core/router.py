from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth.dependencies import Principal, current_principal, require_roles
from app.core.subscriptions import (
    current_plan_name,
    ensure_plan_rows,
    plans_payload,
    set_tenant_plan,
)
from app.db import get_db

router = APIRouter(prefix="/api/v1", tags=["core"])


@router.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "up"}


@router.get("/subscription/plans")
def list_subscription_plans(
    db: Session = Depends(get_db),
    principal: Principal = Depends(current_principal),
):
    ensure_plan_rows(db)
    return {"plans": plans_payload(), "current_plan": current_plan_name(db, principal.tenant_id)}


@router.get("/subscription")
def current_subscription(
    db: Session = Depends(get_db),
    principal: Principal = Depends(current_principal),
):
    ensure_plan_rows(db)
    return {"plan_name": current_plan_name(db, principal.tenant_id)}


@router.post("/subscription/select")
def select_subscription_plan(
    plan_name: str = Query(...),
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles("owner", "admin", "platform_admin")),
):
    subscription = set_tenant_plan(db, principal.tenant_id, plan_name)
    return {"subscription_id": subscription.id, "plan_name": plan_name, "status": subscription.status}
