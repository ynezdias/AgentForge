"""Create the local demo accounts from environment variables.

    python -m app.db.seed_users            # create missing accounts
    python -m app.db.seed_users --reset    # also reset their passwords from env

Credentials come only from DEMO_ADMIN_EMAIL / DEMO_ADMIN_PASSWORD and
DEMO_COMPANY_EMAIL / DEMO_COMPANY_PASSWORD. Accounts are flagged is_demo and
are refused at login when APP_ENV=production; this script also refuses to run
there, so demo credentials can never become production credentials.
"""

import os
import sys

from sqlalchemy import func, select

from app.api.demo import demo_company
from app.core.security import hash_password, is_production
from app.db.session import SessionLocal
from app.models.identity import User

MIN_DEMO_PASSWORD = 6


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        sys.exit(f"{name} is not set; add it to the environment or .env file")
    return value


def upsert(db, email, password, role, company_id, reset):
    if len(password) < MIN_DEMO_PASSWORD:
        sys.exit(f"Demo password for {email} must be at least {MIN_DEMO_PASSWORD} characters")
    user = db.scalar(select(User).where(func.lower(User.email) == email.lower()))
    if user is None:
        db.add(User(email=email.lower(), password_hash=hash_password(password), role=role,
                    company_id=company_id, is_demo=True))
        return "created"
    if user.role != role or not user.is_demo:
        sys.exit(f"{email} already exists as a non-demo or {user.role} account; refusing to change it")
    if reset:
        user.password_hash = hash_password(password)
        user.token_version += 1  # Sign out existing sessions.
        user.company_id = company_id
        return "password reset"
    return "already exists"


def main(reset: bool = False):
    from dotenv import load_dotenv
    load_dotenv()
    if is_production():
        sys.exit("Refusing to create demo accounts when APP_ENV=production")
    admin_email, admin_password = _required("DEMO_ADMIN_EMAIL"), _required("DEMO_ADMIN_PASSWORD")
    company_email, company_password = _required("DEMO_COMPANY_EMAIL"), _required("DEMO_COMPANY_PASSWORD")
    with SessionLocal() as db:
        company = demo_company(db)
        admin = upsert(db, admin_email, admin_password, "admin", None, reset)
        member = upsert(db, company_email, company_password, "company", company.id, reset)
        company_name = company.name
        db.commit()
    print(f"Admin {admin_email}: {admin}")
    print(f"Company user {company_email} ({company_name}): {member}")


if __name__ == "__main__":
    main(reset="--reset" in sys.argv[1:])
