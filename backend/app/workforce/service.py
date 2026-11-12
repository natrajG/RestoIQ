from decimal import Decimal

from app.workforce.schemas import PayrollLineInput
from app.pos.service import money


def calculate_payroll_line(line: PayrollLineInput) -> dict:
    earnings = {name: money(amount) for name, amount in line.earnings.items()}
    deductions = {name: money(amount) for name, amount in line.deductions.items()}
    contributions = {name: money(amount) for name, amount in line.employer_contributions.items()}
    if any(amount < 0 for group in (earnings, deductions, contributions) for amount in group.values()):
        raise ValueError("Payroll inputs cannot be negative")
    gross = money(sum(earnings.values(), Decimal("0")))
    deductions_total = money(sum(deductions.values(), Decimal("0")))
    if deductions_total > gross:
        raise ValueError("Deductions cannot exceed gross pay")
    return {
        "earnings": earnings,
        "deductions": deductions,
        "employer_contributions": contributions,
        "gross_pay": gross,
        "net_pay": money(gross - deductions_total),
        "accountant_reviewed": False,
    }
