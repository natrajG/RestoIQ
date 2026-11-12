from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import Principal, current_principal, require_outlet_access, require_roles
from app.core.audit import audit
from app.db import get_db
from app.models import Employee, PayrollLine, PayrollRun, Shift
from app.workforce.schemas import EmployeeInput, PayrollRunInput, ShiftInput
from app.workforce.repository import add_employee, employee_by_id, employees_for_outlet
from app.workforce.service import calculate_payroll_line

router = APIRouter(prefix="/api/v1/outlets/{outlet_id}", tags=["workforce"])
MANAGERS = ("owner", "manager", "admin")


@router.get("/employees")
def list_employees(outlet_id: int, db: Session = Depends(get_db), principal: Principal = Depends(current_principal)):
    require_outlet_access(db, principal, outlet_id)
    rows = employees_for_outlet(db, principal.tenant_id, outlet_id)
    return [{
        "id": e.id, "display_name": e.display_name, "role": e.role, "email": e.email,
        "monthly_salary": str(e.monthly_salary),
    } for e in rows]


@router.post("/employees", status_code=201)
def create_employee(
    outlet_id: int,
    body: EmployeeInput,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles(*MANAGERS)),
):
    require_outlet_access(db, principal, outlet_id)
    if body.restaurant_id != outlet_id:
        raise HTTPException(422, "Outlet ID mismatch")
    employee = Employee(
        tenant_id=principal.tenant_id, restaurant_id=outlet_id,
        **body.model_dump(exclude={"restaurant_id"}),
    )
    add_employee(db, employee)
    audit(db, principal, "employee_created", "employee", employee.id)
    return {"id": employee.id, "display_name": employee.display_name, "role": employee.role}


@router.post("/shifts", status_code=201)
def create_shift(
    outlet_id: int,
    body: ShiftInput,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles(*MANAGERS)),
):
    require_outlet_access(db, principal, outlet_id)
    if body.restaurant_id != outlet_id or body.ends_at <= body.starts_at:
        raise HTTPException(422, "Provide matching outlet and valid shift times")
    employee = employee_by_id(db, principal.tenant_id, outlet_id, body.employee_id)
    if not employee or not employee.active:
        raise HTTPException(404, "Employee not found")
    shift = Shift(tenant_id=principal.tenant_id, **body.model_dump())
    db.add(shift)
    db.flush()
    audit(db, principal, "shift_scheduled", "shift", shift.id)
    return {"id": shift.id, "employee_id": shift.employee_id, "starts_at": shift.starts_at, "ends_at": shift.ends_at}


@router.post("/payroll/runs", status_code=201)
def create_payroll_run(
    outlet_id: int,
    body: PayrollRunInput,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles(*MANAGERS)),
):
    require_outlet_access(db, principal, outlet_id)
    if body.restaurant_id != outlet_id or body.period_end <= body.period_start:
        raise HTTPException(422, "Provide matching outlet and valid payroll dates")
    run = PayrollRun(
        tenant_id=principal.tenant_id, restaurant_id=outlet_id,
        period_start=body.period_start, period_end=body.period_end, status="draft",
    )
    db.add(run)
    db.flush()
    results = []
    for line in body.lines:
        employee = employee_by_id(db, principal.tenant_id, outlet_id, line.employee_id)
        if not employee:
            raise HTTPException(404, f"Employee {line.employee_id} not found")
        try:
            calculated = calculate_payroll_line(line)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        payroll_line = PayrollLine(
            tenant_id=principal.tenant_id, payroll_run_id=run.id,
            employee_id=line.employee_id, **calculated,
        )
        db.add(payroll_line)
        results.append({
            "employee_id": line.employee_id, "gross_pay": str(payroll_line.gross_pay),
            "net_pay": str(payroll_line.net_pay), "accountant_reviewed": False,
        })
    audit(db, principal, "payroll_run_created", "payroll_run", run.id, {"accountant_reviewed": False})
    return {"id": run.id, "status": run.status, "requires_accountant_review": True, "lines": results}
