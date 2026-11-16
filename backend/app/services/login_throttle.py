"""Sign-in throttling stored in PostgreSQL (works across workers and restarts).

Two independent limits within a rolling window:
  * per email: EMAIL_LIMIT failures lock that email for LOCK_MINUTES. This is the
    primary protection against password guessing.
  * per client IP: IP_LIMIT failures lock the IP. Best-effort, because the
    address is only as trustworthy as the proxy that reports it.

Unknown emails are counted exactly like real ones, so a 429 never reveals
whether an account exists.
"""

import hashlib
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.identity import LoginThrottle

EMAIL_LIMIT = 5
IP_LIMIT = 20
WINDOW = timedelta(minutes=15)
LOCK = timedelta(minutes=15)


def email_key(email: str) -> str:
    return "email:" + hashlib.sha256(email.strip().lower().encode()).hexdigest()[:48]


def client_ip(request) -> str | None:
    if os.environ.get("TRUST_PROXY_HEADERS", "false").lower() == "true":
        forwarded = request.headers.get("x-forwarded-for", "")
        first = forwarded.split(",")[0].strip()
        if first:
            return first[:45]
    return request.client.host if request.client else None


def throttle_keys(email: str, ip: str | None) -> list[tuple[str, int]]:
    keys = [(email_key(email), EMAIL_LIMIT)]
    if ip:
        keys.append((f"ip:{ip}", IP_LIMIT))
    return keys


def seconds_locked(db: Session, keys: list[tuple[str, int]]) -> int:
    now = datetime.now(timezone.utc)
    rows = db.scalars(select(LoginThrottle).where(LoginThrottle.key.in_([k for k, _ in keys]))).all()
    remaining = [(row.locked_until - now).total_seconds() for row in rows
                 if row.locked_until is not None and row.locked_until > now]
    return int(max(remaining)) + 1 if remaining else 0


def record_failure(db: Session, keys: list[tuple[str, int]]) -> None:
    now = datetime.now(timezone.utc)
    for key, limit in keys:
        db.execute(insert(LoginThrottle).values(key=key, failures=0, window_started_at=now)
                   .on_conflict_do_nothing(index_elements=["key"]))
        row = db.scalar(select(LoginThrottle).where(LoginThrottle.key == key).with_for_update())
        if now - row.window_started_at > WINDOW or (row.locked_until and row.locked_until <= now):
            row.failures, row.window_started_at, row.locked_until = 0, now, None
        row.failures += 1
        if row.failures >= limit:
            row.locked_until = now + LOCK


def record_success(db: Session, email: str) -> None:
    # Only the email counter resets; a shared IP keeps its history.
    db.execute(delete(LoginThrottle).where(LoginThrottle.key == email_key(email)))
