"""Create (or top up) a sales-demo restaurant with a month of dummy data.

Works in any environment, including production:
    docker compose exec -T api python -m app.demo_restaurant [--password PASS]
"""
import argparse
import secrets

from sqlalchemy import select

from app.auth.service import hash_password
from app.db import SessionLocal, set_tenant_context
from app.models import Tenant, User
from app.seed import build_demo

TENANT = "RestoIQ Demo Restaurant"
OWNER = "demo@restoiq.in"
STAFF_DOMAIN = "demo.restoiq.in"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--password", help="login password (random if omitted and the account is new)")
    parser.add_argument("--reset-password", action="store_true", help="set the password on an existing demo account")
    args = parser.parse_args()
    password = args.password or secrets.token_urlsafe(9) + "a1"
    with SessionLocal() as db:
        existed = db.scalar(select(User.id).where(User.email == OWNER)) is not None
    build_demo(TENANT, OWNER, password, STAFF_DOMAIN, volume=3)
    if existed and (args.password or args.reset_password):
        with SessionLocal() as db:
            tenant = db.scalar(select(Tenant).where(Tenant.name == TENANT))
            set_tenant_context(db, tenant.id)
            db.scalar(select(User).where(User.email == OWNER)).password_hash = hash_password(password)
            db.commit()
    print(f"Login: {OWNER}")
    print("Password: " + (password if (not existed or args.password or args.reset_password) else "unchanged (use --reset-password)"))
    print(f"Staff logins: cashier@, server@, kitchen@, cleaner@{STAFF_DOMAIN} (same password)")


if __name__ == "__main__":
    main()
