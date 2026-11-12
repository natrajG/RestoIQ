from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Employee


def employee_by_id(db: Session, tenant_id: int, outlet_id: int, employee_id: int) -> Employee | None:
    return db.scalar(select(Employee).where(
        Employee.id == employee_id, Employee.tenant_id == tenant_id,
        Employee.restaurant_id == outlet_id,
    ))


def employees_for_outlet(db: Session, tenant_id: int, outlet_id: int) -> list[Employee]:
    return db.scalars(select(Employee).where(
        Employee.tenant_id == tenant_id, Employee.restaurant_id == outlet_id,
        Employee.active.is_(True),
    ).order_by(Employee.display_name)).all()


def add_employee(db: Session, employee: Employee) -> Employee:
    db.add(employee)
    db.flush()
    return employee
