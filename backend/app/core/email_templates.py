"""Plain-text email bodies."""
from app.core.config import settings

SIGN_OFF = "\n— Team RestoIQ"


def welcome(name: str, trial_days: int) -> tuple[str, str]:
    return "Welcome to RestoIQ", (
        f"Hi {name},\n\nYour RestoIQ workspace is ready and your first month is free ({trial_days} days).\n"
        f"Sign in: {settings.app_public_url}\n\nA good first step is the Setup guide inside the app: add your menu, "
        f"tables and GST settings, then take your first order.\n{SIGN_OFF}")


def receipt(name: str, number: str, total: float, period_start: str, period_end: str) -> tuple[str, str]:
    return f"Payment received: {number}", (
        f"Hi {name},\n\nThank you. We received ₹{total:,.2f} for invoice {number}.\n"
        f"Your plan is active from {period_start} to {period_end}.\n"
        f"You can print the invoice from Subscription in the app: {settings.app_public_url}/billing\n{SIGN_OFF}")


def reminder(name: str, days: int, trial: bool, ended: bool = False) -> tuple[str, str]:
    what = "free trial" if trial else "plan"
    when = "today" if days == 0 else "tomorrow" if days == 1 else f"in {days} days"
    if ended:
        return f"Your RestoIQ {what} has ended", (
            f"Hi {name},\n\nYour RestoIQ {what} has ended. Renew here to keep your POS running:\n"
            f"{settings.app_public_url}/billing\n\nYour data stays safe either way.\n{SIGN_OFF}")
    return f"Your RestoIQ {what} ends {when}", (
        f"Hi {name},\n\nYour RestoIQ {what} ends {when}. To keep your POS running without a break, renew here:\n"
        f"{settings.app_public_url}/billing\n\nYour data stays safe either way.\n{SIGN_OFF}")


def password_reset(link: str, minutes: int) -> tuple[str, str]:
    return "Reset your RestoIQ password", (
        f"We received a request to reset your RestoIQ password.\n\n{link}\n\n"
        f"This link works once and expires in {minutes} minutes. If you did not ask for it, ignore this email; "
        f"your password has not changed.\n{SIGN_OFF}")
