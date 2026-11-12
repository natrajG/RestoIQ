from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import Principal, require_outlet_access, require_roles
from app.db import get_db, set_tenant_context
from app.models import (
    Camera, DiningTable, MenuItem, OutletMembership, Restaurant,
)

router = APIRouter(prefix="/api/v1/outlets/{outlet_id}", tags=["onboarding"])
MANAGERS = ("owner", "admin", "manager")


@router.get("/onboarding")
def onboarding_status(outlet_id: int, principal: Principal = Depends(require_roles(*MANAGERS)), db: Session = Depends(get_db)):
    set_tenant_context(db, principal.tenant_id)
    require_outlet_access(db, principal, outlet_id)
    tid = principal.tenant_id
    outlet = db.get(Restaurant, outlet_id)

    def count(model, *conds) -> int:
        return db.scalar(select(func.count()).select_from(model).where(*conds)) or 0

    tables = count(DiningTable, DiningTable.tenant_id == tid, DiningTable.restaurant_id == outlet_id)
    cams = list(db.scalars(select(Camera).where(Camera.tenant_id == tid, Camera.restaurant_id == outlet_id)))
    zoned = [c for c in cams if c.regions]
    staff = count(OutletMembership, OutletMembership.tenant_id == tid, OutletMembership.outlet_id == outlet_id, OutletMembership.role != "owner")
    menu = count(MenuItem, MenuItem.tenant_id == tid, MenuItem.restaurant_id == outlet_id)

    steps = [
        {"key": "tables", "title": "Add your floors and tables", "route": "/tables", "done": tables > 0,
         "detail": f"{tables} table(s) added" if tables else "Create tables per floor so cameras and orders can refer to them."},
        {"key": "cameras", "title": "Add cameras for each floor", "route": "/cameras", "done": len(cams) > 0,
         "detail": f"{len(cams)} camera(s)" if cams else "Add every camera needed to see all tables on each floor."},
        {"key": "zones", "title": "Outline tables in camera views", "route": "/cameras", "done": bool(cams) and len(zoned) == len(cams),
         "detail": f"{len(zoned)} of {len(cams)} camera(s) have table zones" if cams else "Upload a screenshot and draw each table."},
    ]
    steps.append({"key": "menu", "title": "Add menu items and GST", "route": "/menu", "done": menu > 0,
                  "detail": f"{menu} menu item(s)" if menu else "Add the dishes, prices and GST rates sold at this outlet."})
    steps.append({"key": "staff", "title": "Invite your staff", "route": "/staff", "done": staff > 0,
                  "detail": f"{staff} staff login(s) with access" if staff > 0 else "Create logins for managers, waiters, kitchen and cleaners."})
    done = sum(s["done"] for s in steps)
    return {"outlet": outlet.name, "steps": steps, "done": done, "total": len(steps), "complete": done == len(steps)}
