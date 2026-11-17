"""Deployment configuration: hosted DB URLs, the internal-token gate, admin bootstrap."""

import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db.session import normalize_database_url
from app.main import app


@pytest.mark.parametrize("given, expected", [
    ("postgres://u:p@host:5432/db", "postgresql+psycopg://u:p@host:5432/db"),        # Render / Heroku style
    ("postgresql://u:p@host/db?sslmode=require", "postgresql+psycopg://u:p@host/db?sslmode=require"),
    ("postgresql+psycopg://u:p@host/db", "postgresql+psycopg://u:p@host/db"),         # already explicit
    ("sqlite://", "sqlite://"),
])
def test_database_url_normalization(given, expected):
    assert normalize_database_url(given) == expected


def test_internal_token_gate(monkeypatch):
    client = TestClient(app)
    monkeypatch.delenv("INTERNAL_API_TOKEN", raising=False)
    assert client.get("/api/v1/auth/me").status_code == 401  # Gate off: normal auth applies.
    monkeypatch.setenv("INTERNAL_API_TOKEN", "proxy-shared-secret-value")
    assert client.get("/health").status_code == 200           # Health checks stay open.
    assert client.get("/api/v1/auth/me").status_code == 404   # Direct callers see nothing.
    assert client.get("/api/v1/auth/me", headers={"x-internal-token": "wrong"}).status_code == 404
    assert client.post("/api/v1/auth/login", json={}).status_code == 404
    assert client.get("/api/v1/auth/me", headers={"x-internal-token": "proxy-shared-secret-value"}).status_code == 401


@pytest.mark.skipif(os.environ.get("RUN_DB_TESTS") != "1", reason="Requires local migrated PostgreSQL")
def test_bootstrap_admin_creates_once_and_never_overwrites(monkeypatch, capsys):
    from sqlalchemy import delete, select
    from app.core.security import verify_password
    from app.db import bootstrap_admin
    from app.db.session import SessionLocal
    from app.models.identity import User

    email = f"bootstrap-{uuid4().hex[:8]}@example.test"
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", email)
    try:
        monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "short")
        assert bootstrap_admin.main() == 1  # Weak password refused.
        monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "a-long-production-password")
        assert bootstrap_admin.main() == 0
        monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "a-different-long-password")
        assert bootstrap_admin.main() == 0  # Existing account left unchanged.
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.email == email))
            assert user.role == "admin" and user.is_demo is False and user.company_id is None
            assert verify_password("a-long-production-password", user.password_hash)
    finally:
        with SessionLocal() as db:
            db.execute(delete(User).where(User.email == email))
            db.commit()
    monkeypatch.delenv("BOOTSTRAP_ADMIN_EMAIL")
    monkeypatch.delenv("BOOTSTRAP_ADMIN_PASSWORD")
    assert bootstrap_admin.main() == 0  # Not configured: no-op.
