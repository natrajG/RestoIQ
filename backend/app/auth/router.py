import logging
import secrets
from datetime import timedelta

import redis
import hashlib
from fastapi import BackgroundTasks
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import Principal, current_principal
from app.core.config import settings
from app.auth.repository import user_by_email
from app.auth.schemas import ForgotPasswordInput, LoginInput, ResetPasswordInput, SignupInput
from app.auth.service import create_access_token, hash_password, verify_password
from app.core.subscriptions import subscription_state, PLAN_DEFINITIONS, PLAN_RESTOIQ, ensure_plan_rows
from app.db import get_db, set_tenant_context
from app.core import email_templates, mailer
from app.models import PasswordResetToken, Restaurant, Subscription, SubscriptionPlan, Tenant, TenantProfile, User, now_utc

TRIAL_DAYS = 30
SIGNUPS_PER_HOUR_PER_IP = 5
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


LOGIN_WINDOW_SECONDS = 900
DUMMY_HASH = hash_password("not-a-real-password-1")  # verified when the account is unknown so timing does not reveal it


def _client_ip(request: Request) -> str:
    # nginx appends the address it saw as the last X-Forwarded-For entry; earlier entries are client-supplied
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[-1].strip()[:64]
    return request.client.host if request.client else "unknown"


@router.post("/login")
def login(body: LoginInput, request: Request, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    message = "Too many sign-in attempts. Please wait 15 minutes and try again."
    _rate_limit(request, "login-ip", 40, message, LOGIN_WINDOW_SECONDS)
    _rate_limit(request, "login-acct", 8, message, LOGIN_WINDOW_SECONDS, subject=email)
    user = user_by_email(db, email)
    password_ok = verify_password(body.password, user.password_hash if user else DUMMY_HASH)
    if not user or not user.is_active or not password_ok:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    try:
        redis.Redis.from_url(settings.redis_url, socket_timeout=1).delete(f"login-acct:{hashlib.sha256(email.encode()).hexdigest()[:24]}")
    except redis.RedisError:
        pass
    token = create_access_token(user.id, user.tenant_id, user.role)
    response = JSONResponse({"user": {"id": user.id, "email": user.email, "role": user.role}})
    response.set_cookie(
        "restaurant_session", token, httponly=True, secure=settings.cookie_secure,
        samesite="strict", max_age=settings.jwt_expiry_minutes * 60, path="/",
    )
    return response


def _set_session_cookie(response: JSONResponse, token: str) -> None:
    response.set_cookie(
        "restaurant_session", token, httponly=True, secure=settings.cookie_secure,
        samesite="strict", max_age=settings.jwt_expiry_minutes * 60, path="/",
    )


def _rate_limit(request: Request, name: str, limit: int, message: str, window: int = 3600, subject: str | None = None) -> None:
    who = hashlib.sha256(subject.encode()).hexdigest()[:24] if subject else _client_ip(request)
    try:
        client = redis.Redis.from_url(settings.redis_url, socket_timeout=1)
        key = f"{name}:{who}"
        count = client.incr(key)
        if count == 1:
            client.expire(key, window)
        if count > limit:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, message)
    except redis.RedisError:
        logger.warning("Rate limiter unavailable")


def _enforce_signup_rate_limit(request: Request) -> None:
    _rate_limit(request, "signup-rate", SIGNUPS_PER_HOUR_PER_IP, "Too many sign-up attempts. Try again later.")


@router.post("/signup", status_code=201)
def signup(body: SignupInput, request: Request, background: BackgroundTasks, db: Session = Depends(get_db)):
    if body.plan_name not in PLAN_DEFINITIONS:
        raise HTTPException(422, f"plan_name must be {PLAN_RESTOIQ}")
    _enforce_signup_rate_limit(request)
    if user_by_email(db, body.email):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")

    tenant_name = body.restaurant_name
    if db.scalar(select(Tenant.id).where(Tenant.name == tenant_name)):
        tenant_name = f"{body.restaurant_name} #{secrets.token_hex(2)}"
    tenant = Tenant(name=tenant_name)
    db.add(tenant)
    db.flush()
    set_tenant_context(db, tenant.id)

    ensure_plan_rows(db)
    db.flush()
    plan = db.scalar(select(SubscriptionPlan).where(SubscriptionPlan.name == body.plan_name, SubscriptionPlan.active.is_(True)))
    if not plan:
        raise HTTPException(500, "Subscription plans are not configured")
    trial_ends = now_utc() + timedelta(days=TRIAL_DAYS)
    db.add(Subscription(tenant_id=tenant.id, plan_id=plan.id, status="trial", billing_cycle=body.billing_cycle, starts_at=now_utc(), ends_at=trial_ends))

    user = User(tenant_id=tenant.id, email=body.email, password_hash=hash_password(body.password), role="owner", full_name=body.owner_name)
    db.add(user)
    db.add(Restaurant(
        tenant_id=tenant.id, name=body.restaurant_name, timezone="Asia/Kolkata", currency="INR",
        state_code=body.state_code,
        tax_config={"currency": "INR", "tax_mode": "configurable", "accountant_review_required": True},
    ))
    db.add(TenantProfile(
        tenant_id=tenant.id, owner_name=body.owner_name, mobile=body.mobile, address_line=body.address_line,
        city=body.city, state_code=body.state_code, pincode=body.pincode, gstin=body.gstin, trial_ends_at=trial_ends,
    ))
    db.flush()

    user_id, user_email = user.id, user.email
    token = create_access_token(user_id, tenant.id, user.role)
    # Commit before replying: otherwise the session cookie can reach the browser before the new account is visible.
    db.commit()
    response = JSONResponse(
        {"user": {"id": user_id, "email": user_email, "role": "owner"}, "trial_ends_at": trial_ends.isoformat()},
        status_code=201,
    )
    _set_session_cookie(response, token)
    background.add_task(mailer.send_safe, user_email, *email_templates.welcome(body.owner_name, TRIAL_DAYS))
    return response


RESET_MINUTES = 60
RESET_SENT = {"message": "If that email is registered, a reset link is on its way."}


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@router.post("/forgot-password")
def forgot_password(body: ForgotPasswordInput, request: Request, background: BackgroundTasks, db: Session = Depends(get_db)):
    if not mailer.configured():
        raise HTTPException(503, "Password reset is not available right now. Please contact support.")
    _rate_limit(request, "reset-request", 10, "Too many requests. Try again later.")
    user = user_by_email(db, body.email.strip().lower())
    if user and user.is_active:
        token = secrets.token_urlsafe(32)
        db.add(PasswordResetToken(user_id=user.id, token_hash=_hash_token(token),
                                  expires_at=now_utc() + timedelta(minutes=RESET_MINUTES)))
        # The token sits in the URL fragment so it never reaches server logs or Referer headers
        link = f"{settings.app_public_url.rstrip('/')}/reset-password#token={token}"
        background.add_task(mailer.send_safe, user.email, *email_templates.password_reset(link, RESET_MINUTES))
    return RESET_SENT  # identical whether or not the address is registered


@router.post("/reset-password")
def reset_password(body: ResetPasswordInput, request: Request, db: Session = Depends(get_db)):
    _rate_limit(request, "reset-attempt", 20, "Too many attempts. Try again later.")
    row = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == _hash_token(body.token)).with_for_update())
    if not row or row.used_at is not None or row.expires_at <= now_utc():
        raise HTTPException(400, "This reset link is invalid or has expired. Request a new one.")
    user = db.get(User, row.user_id)
    if not user or not user.is_active:
        raise HTTPException(400, "This reset link is invalid or has expired. Request a new one.")
    set_tenant_context(db, user.tenant_id)
    user.password_hash = hash_password(body.password)
    row.used_at = now_utc()
    for other in db.scalars(select(PasswordResetToken).where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))):
        other.used_at = now_utc()
    return {"message": "Password updated. You can now sign in."}


@router.post("/logout", status_code=204)
def logout():
    response = JSONResponse(status_code=204, content=None)
    response.delete_cookie("restaurant_session", path="/", httponly=True, secure=settings.cookie_secure, samesite="strict")
    return response


@router.get("/me")
def me(principal: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    state = subscription_state(db, principal.tenant_id)
    user = db.get(User, principal.user_id)
    return {
        "id": principal.user_id, "email": principal.email, "role": principal.role,
        "tenant_id": principal.tenant_id, "full_name": user.full_name if user else None,
        "subscription": {"status": state["status"], "days_left": state["days_left"],
                         "trial_ends_at": state["trial_ends_at"], "locked": state["locked"]},
    }
