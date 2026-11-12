from collections.abc import Sequence
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Subscription, SubscriptionPlan, now_utc

PLAN_RESTOIQ = "RESTOIQ_POS"
DEFAULT_PLAN = PLAN_RESTOIQ
BILLING_CYCLES = ("monthly", "yearly")
MONTHLY_PRICE_INR = 499
YEARLY_PRICE_INR = 5999

PLAN_DEFINITIONS: dict[str, dict] = {
    PLAN_RESTOIQ: {
        "description": "Complete restaurant POS (menu, GST billing, KOT, payments, reports) with live camera table monitoring, staff tasks and revenue insights.",
        "includes_native_pos": True,
    },
}


def supported_plan_names() -> tuple[str]:
    return (PLAN_RESTOIQ,)


def ensure_plan_rows(db: Session) -> None:
    plans = db.scalars(select(SubscriptionPlan)).all()
    by_name = {plan.name: plan for plan in plans}
    for name, entitlements in PLAN_DEFINITIONS.items():
        plan = by_name.get(name)
        if not plan:
            db.add(SubscriptionPlan(name=name, entitlements=entitlements, active=True))
            continue
        plan.entitlements = entitlements
        plan.active = True
    for plan in plans:
        if plan.name not in PLAN_DEFINITIONS:
            plan.active = False


def _latest_subscription(db: Session, tenant_id: int) -> Subscription | None:
    return db.scalar(
        select(Subscription)
        .where(Subscription.tenant_id == tenant_id)
        .order_by(Subscription.starts_at.desc(), Subscription.id.desc())
    )


def current_plan_name(db: Session, tenant_id: int) -> str:
    active_subscription = _latest_subscription(db, tenant_id)
    if not active_subscription:
        return DEFAULT_PLAN
    plan = db.get(SubscriptionPlan, active_subscription.plan_id)
    if not plan or not plan.active or plan.name not in PLAN_DEFINITIONS:
        return DEFAULT_PLAN
    return plan.name


def set_tenant_plan(db: Session, tenant_id: int, plan_name: str) -> Subscription:
    if plan_name not in PLAN_DEFINITIONS:
        raise HTTPException(
            422,
            f"plan_name must be {PLAN_RESTOIQ}",
        )
    ensure_plan_rows(db)
    db.flush()
    plan = db.scalar(
        select(SubscriptionPlan).where(
            SubscriptionPlan.name == plan_name,
            SubscriptionPlan.active.is_(True),
        )
    )
    if not plan:
        raise HTTPException(500, "Subscription plans are not configured")
    current = _latest_subscription(db, tenant_id)
    if current and current.plan_id == plan.id and current.status == "active":
        return current
    if current and current.status in {"trial", "active"}:
        current.status = "superseded"
    subscription = Subscription(
        tenant_id=tenant_id,
        plan_id=plan.id,
        status="active",
        starts_at=now_utc(),
    )
    db.add(subscription)
    db.flush()
    return subscription


def plans_payload(names: Sequence[str] | None = None) -> list[dict]:
    plan_names = names or PLAN_DEFINITIONS.keys()
    return [
        {
            "name": name,
            "entitlements": PLAN_DEFINITIONS[name],
            "default": name == DEFAULT_PLAN,
        }
        for name in plan_names
        if name in PLAN_DEFINITIONS
    ]


GRACE_DAYS = 3  # a paid plan keeps working this long after it ends, so a late renewal never stops a busy service


def subscription_state(db: Session, tenant_id: int) -> dict:
    """status: trial | active | grace (paid period over, still working) | expired (locked). ends_at None = never expires."""
    sub = _latest_subscription(db, tenant_id)
    if not sub:
        return {"status": "none", "trial_ends_at": None, "days_left": None, "locked": False}
    now = now_utc()
    ends = sub.ends_at
    status, locked, days_left = sub.status, False, None
    if ends is not None:
        days_left = max((ends - now).days, 0)
        if sub.status == "trial" and ends <= now:
            status, locked = "expired", True
        elif sub.status == "active" and ends <= now:
            grace_over = now >= ends + timedelta(days=GRACE_DAYS)
            status, locked = ("expired", True) if grace_over else ("grace", False)
            days_left = 0
    return {"status": status, "trial_ends_at": ends, "days_left": days_left, "locked": locked}
