"""Create real users and signed tokens inside a test transaction."""

from uuid import uuid4

from app.core.security import create_access_token, hash_password
from app.models.identity import Company, User

TEST_PASSWORD = "correct-horse-battery"
_HASH = hash_password(TEST_PASSWORD)  # Hash once; scrypt is deliberately slow.


def make_company(db, name=None):
    company = Company(name=name or f"Company {uuid4().hex[:8]}")
    db.add(company)
    db.flush()
    return company


def make_user(db, role, company=None, email=None, **fields):
    user = User(email=email or f"{role}-{uuid4().hex[:8]}@example.test", password_hash=_HASH,
                role=role, company_id=company.id if company else None, **fields)
    db.add(user)
    db.flush()
    return user


def headers(user):
    token, _ = create_access_token(user.id, user.role, user.token_version)
    return {"Authorization": f"Bearer {token}"}
