from decimal import Decimal

import pytest

from app.pos.service import calculate_order_totals
from app.main import app
from app.models import Payment, Refund
from app.core.subscriptions import PLAN_RESTOIQ, supported_plan_names
from app.workforce.schemas import PayrollLineInput
from app.workforce.service import calculate_payroll_line
from sqlalchemy import UniqueConstraint


def test_order_totals_use_configured_tax_and_discount():
    subtotal, tax, discount, total = calculate_order_totals(
        [(2, Decimal("100.00"), Decimal("5"))], Decimal("10")
    )
    assert (subtotal, tax, discount, total) == (
        Decimal("200.00"), Decimal("10.00"), Decimal("10.00"), Decimal("200.00")
    )


def test_order_discount_cannot_exceed_amount_due():
    with pytest.raises(ValueError, match="Discount cannot exceed"):
        calculate_order_totals([(1, Decimal("10"), Decimal("0"))], Decimal("11"))


def test_payroll_is_input_driven_and_not_marked_compliant():
    result = calculate_payroll_line(PayrollLineInput(
        employee_id=1,
        earnings={"base": Decimal("30000"), "tips": Decimal("1000")},
        deductions={"configured_deduction": Decimal("2000")},
        employer_contributions={"configured_contribution": Decimal("500")},
    ))
    assert result["gross_pay"] == Decimal("31000.00")
    assert result["net_pay"] == Decimal("29000.00")
    assert result["accountant_reviewed"] is False


def test_payroll_rejects_negative_configured_inputs():
    with pytest.raises(ValueError, match="cannot be negative"):
        calculate_payroll_line(PayrollLineInput(employee_id=1, earnings={"base": Decimal("-1")}))


@pytest.mark.parametrize(
    ("path", "model"),
    [
        ("/api/v1/orders/{order_id}/payments", Payment),
        ("/api/v1/orders/{order_id}/refunds", Refund),
    ],
)
def test_financial_writes_require_idempotency_and_enforce_unique_keys(path, model):
    operation = app.openapi()["paths"][path]["post"]
    key_parameter = next(
        parameter for parameter in operation["parameters"]
        if parameter["name"] == "Idempotency-Key"
    )
    assert key_parameter["in"] == "header"
    assert key_parameter["required"] is True
    unique_constraints = [
        constraint for constraint in model.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    ]
    assert any(
        {column.name for column in constraint.columns}
        == {"tenant_id", "order_id", "idempotency_key"}
        for constraint in unique_constraints
    )


def test_subscription_supports_a_single_plan():
    assert supported_plan_names() == (PLAN_RESTOIQ,)
