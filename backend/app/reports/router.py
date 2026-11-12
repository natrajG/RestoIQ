from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import Principal, require_outlet_access, require_roles
from app.db import get_db, set_tenant_context
from app.models import GeneratedReport, Restaurant
from app.reports.builder import PERIOD_DAYS, build_report
from app.reports.insights import sales_insights

router = APIRouter(prefix="/api/v1", tags=["reports"])


@router.get("/outlets/{outlet_id}/analytics/insights")
def insights(
    outlet_id: int, days: int = 28, db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles("owner", "manager", "admin", "analyst")),
):
    set_tenant_context(db, principal.tenant_id)
    require_outlet_access(db, principal, outlet_id)
    outlet = db.scalar(select(Restaurant).where(Restaurant.id == outlet_id, Restaurant.tenant_id == principal.tenant_id))
    if not outlet:
        raise HTTPException(404, "Outlet not found")
    return sales_insights(db, principal.tenant_id, outlet, max(1, min(days, 365)))


@router.get("/outlets/{outlet_id}/reports/{period}")
def owner_report(
    outlet_id: int, period: str, db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles("owner", "manager", "admin", "analyst")),
):
    if period not in PERIOD_DAYS:
        raise HTTPException(404, "period must be weekly or monthly")
    set_tenant_context(db, principal.tenant_id)
    require_outlet_access(db, principal, outlet_id)
    outlet = db.scalar(select(Restaurant).where(Restaurant.id == outlet_id, Restaurant.tenant_id == principal.tenant_id))
    if not outlet:
        raise HTTPException(404, "Outlet not found")
    return build_report(db, principal.tenant_id, outlet, period)


@router.get("/outlets/{outlet_id}/reports")
def saved_reports(
    outlet_id: int, db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles("owner", "manager", "admin", "analyst")),
):
    """History of automatically generated reports (newest first)."""
    set_tenant_context(db, principal.tenant_id)
    require_outlet_access(db, principal, outlet_id)
    rows = db.scalars(select(GeneratedReport).where(
        GeneratedReport.tenant_id == principal.tenant_id, GeneratedReport.restaurant_id == outlet_id,
    ).order_by(GeneratedReport.id.desc()).limit(60))
    return {"reports": [{"id": r.id, "period": r.period, "period_end": r.period_end.isoformat(), "payload": r.payload} for r in rows]}
