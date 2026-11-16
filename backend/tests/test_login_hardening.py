"""Sign-in throttling and server-side logout (PostgreSQL, rolled back per test)."""

import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import engine, get_db
from app.main import app
from app.models.identity import LoginThrottle, RevokedToken
from app.services import login_throttle
from tests.auth_helpers import TEST_PASSWORD, make_company, make_user

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1", reason="Requires local migrated PostgreSQL"
)


@pytest.fixture
def env():
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            with Session(bind=connection, join_transaction_mode="create_savepoint") as db:
                app.dependency_overrides[get_db] = lambda: db
                try:
                    user = make_user(db, "company", make_company(db))
                    db.commit()
                    with TestClient(app) as client:
                        yield SimpleNamespace(client=client, db=db, user=user)
                finally:
                    app.dependency_overrides.pop(get_db, None)
        finally:
            transaction.rollback()


def attempt(env, email, password, headers=None):
    return env.client.post("/api/v1/auth/login", headers=headers or {},
                           json={"email": email, "password": password, "portal": "company"})


def test_email_locks_after_repeated_failures_even_for_correct_password(env):
    for _ in range(login_throttle.EMAIL_LIMIT):
        assert attempt(env, env.user.email, "wrong-password").status_code == 401
    locked = attempt(env, env.user.email, TEST_PASSWORD)
    assert locked.status_code == 429
    assert int(locked.headers["retry-after"]) > 0
    assert "Too many sign-in attempts" in locked.json()["detail"]


def test_unknown_email_is_throttled_identically(env):
    statuses = [attempt(env, "nobody@example.test", "x").status_code
                for _ in range(login_throttle.EMAIL_LIMIT + 1)]
    assert statuses == [401] * login_throttle.EMAIL_LIMIT + [429]


def test_success_resets_the_email_counter(env):
    for _ in range(login_throttle.EMAIL_LIMIT - 1):
        attempt(env, env.user.email, "wrong-password")
    assert attempt(env, env.user.email, TEST_PASSWORD).status_code == 200
    for _ in range(login_throttle.EMAIL_LIMIT - 1):
        assert attempt(env, env.user.email, "wrong-password").status_code == 401


def test_lock_expires(env):
    for _ in range(login_throttle.EMAIL_LIMIT):
        attempt(env, env.user.email, "wrong-password")
    row = env.db.get(LoginThrottle, login_throttle.email_key(env.user.email))
    row.locked_until = datetime.now(timezone.utc) - timedelta(seconds=1)
    env.db.commit()
    assert attempt(env, env.user.email, TEST_PASSWORD).status_code == 200


def test_ip_limit_spans_different_emails(env):
    for i in range(login_throttle.IP_LIMIT):
        attempt(env, f"spray-{i}@example.test", "x")
    assert attempt(env, env.user.email, TEST_PASSWORD).status_code == 429


def test_forwarded_ip_only_trusted_when_configured(env, monkeypatch):
    spoofed = {"X-Forwarded-For": "203.0.113.9"}
    for i in range(login_throttle.IP_LIMIT):
        attempt(env, f"spray-{i}@example.test", "x", spoofed)
    # Untrusted: the header is ignored, so the real client IP is the one locked.
    assert env.db.get(LoginThrottle, "ip:203.0.113.9") is None
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "true")
    attempt(env, "another@example.test", "x", spoofed)
    assert env.db.get(LoginThrottle, "ip:203.0.113.9").failures == 1


def test_logout_revokes_only_that_token(env):
    first = attempt(env, env.user.email, TEST_PASSWORD).json()["access_token"]
    second = attempt(env, env.user.email, TEST_PASSWORD).json()["access_token"]
    auth = {"Authorization": f"Bearer {first}"}
    assert env.client.get("/api/v1/auth/me", headers=auth).status_code == 200
    assert env.client.post("/api/v1/auth/logout", headers=auth).status_code == 200
    assert env.client.get("/api/v1/auth/me", headers=auth).status_code == 401
    assert env.client.get("/api/v1/invoices", headers=auth).status_code == 401
    # Idempotent, and other sessions of the same user are unaffected.
    assert env.client.post("/api/v1/auth/logout", headers=auth).status_code == 200
    assert env.client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {second}"}).status_code == 200
    assert env.client.post("/api/v1/auth/logout", headers={"Authorization": "Bearer junk"}).status_code == 200
    assert env.client.post("/api/v1/auth/logout").status_code == 200


def test_logout_prunes_expired_revocations(env):
    env.db.add(RevokedToken(jti="stale", expires_at=datetime.now(timezone.utc) - timedelta(hours=1)))
    env.db.commit()
    token = attempt(env, env.user.email, TEST_PASSWORD).json()["access_token"]
    env.client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert env.db.get(RevokedToken, "stale") is None
    assert len(env.db.scalars(select(RevokedToken)).all()) == 1
