"""Create the first real (non-demo) admin from environment variables, once.

    BOOTSTRAP_ADMIN_EMAIL=...  BOOTSTRAP_ADMIN_PASSWORD=...  python -m app.db.bootstrap_admin

Runs at container start (see docker-entrypoint.sh), because some hosts offer no
shell. It is idempotent and conservative: an existing account with that email
is never modified, and weak passwords are refused. Remove the variables from
the host once the admin exists.
"""

import os
import sys

from sqlalchemy import func, select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.identity import User

MIN_PASSWORD = 12


def main() -> int:
    email = os.environ.get("BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
    password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "")
    if not email and not password:
        return 0
    if not email or "@" not in email:
        print("BOOTSTRAP_ADMIN_EMAIL is missing or invalid; skipping admin bootstrap", file=sys.stderr)
        return 1
    if len(password) < MIN_PASSWORD:
        print(f"BOOTSTRAP_ADMIN_PASSWORD must be at least {MIN_PASSWORD} characters; skipping", file=sys.stderr)
        return 1
    with SessionLocal() as db:
        if db.scalar(select(User).where(func.lower(User.email) == email)) is not None:
            print(f"Admin bootstrap: {email} already exists; left unchanged")
            return 0
        db.add(User(email=email, password_hash=hash_password(password), role="admin", is_demo=False))
        db.commit()
    print(f"Admin bootstrap: created {email}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
