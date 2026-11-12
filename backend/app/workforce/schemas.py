from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, StringConstraints
from typing_extensions import Annotated


class EmployeeInput(BaseModel):
    restaurant_id: int
    display_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
    role: str = Field(min_length=1, max_length=64)
    email: str | None = Field(default=None, max_length=254)
    monthly_salary: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)


class ShiftInput(BaseModel):
    restaurant_id: int
    employee_id: int
    starts_at: datetime
    ends_at: datetime


class PayrollLineInput(BaseModel):
    employee_id: int
    earnings: dict[str, Decimal] = Field(default_factory=dict)
    deductions: dict[str, Decimal] = Field(default_factory=dict)
    employer_contributions: dict[str, Decimal] = Field(default_factory=dict)


class PayrollRunInput(BaseModel):
    restaurant_id: int
    period_start: datetime
    period_end: datetime
    lines: list[PayrollLineInput] = Field(min_length=1)
