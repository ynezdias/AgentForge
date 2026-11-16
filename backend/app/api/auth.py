from datetime import datetime, timezone
import jwt
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import (AuthConfigurationError, burn_password_check, create_access_token,
                               decode_access_token, is_production, verify_password)
from app.db.session import get_db
from app.models.identity import Company, RevokedToken, User
from app.services.login_throttle import (client_ip, record_failure, record_success,
                                         seconds_locked, throttle_keys)

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])
INVALID = HTTPException(401, "Email or password is incorrect")


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)
    portal: Literal["admin", "company"]


def user_profile(db: Session, user: User) -> dict:
    company = db.get(Company, user.company_id) if user.company_id else None
    return {"id": user.id, "email": user.email, "role": user.role,
            "company_id": user.company_id, "company_name": company.name if company else None,
            "is_demo": user.is_demo}


def _reject(db: Session, keys) -> None:
    record_failure(db, keys)
    db.commit()
    raise INVALID


@router.post("/login")
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    keys = throttle_keys(payload.email, client_ip(request))
    locked = seconds_locked(db, keys)
    if locked:
        minutes = max(1, round(locked / 60))
        raise HTTPException(429, f"Too many sign-in attempts. Try again in about {minutes} minute{'s' if minutes != 1 else ''}.",
                            headers={"Retry-After": str(locked)})
    user = db.scalar(select(User).where(func.lower(User.email) == payload.email.strip().lower()))
    if user is None:
        burn_password_check(payload.password)
        _reject(db, keys)
    if not verify_password(payload.password, user.password_hash):
        _reject(db, keys)
    if not user.is_active or (user.is_demo and is_production()):
        _reject(db, keys)
    if user.role != payload.portal:
        # Only reachable with the correct password, so this reveals nothing new.
        other = "Admin" if user.role == "admin" else "Company"
        raise HTTPException(403, f"This account signs in through the {other} portal")
    try:
        token, expires_at = create_access_token(user.id, user.role, user.token_version)
    except AuthConfigurationError:
        raise HTTPException(503, "Authentication is not configured on the server") from None
    user.last_login_at = datetime.now(timezone.utc)
    record_success(db, payload.email)
    db.commit()
    return {"access_token": token, "token_type": "bearer", "expires_at": expires_at,
            "user": user_profile(db, user)}


@router.get("/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return user_profile(db, user)


@router.post("/logout")
def logout(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    """Revoke this token server-side. Idempotent: an invalid or missing token is a no-op."""
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() == "bearer" and token:
        try:
            claims = decode_access_token(token)
        except (jwt.InvalidTokenError, AuthConfigurationError):
            return {"status": "signed_out"}
        expires = datetime.fromtimestamp(claims["exp"], tz=timezone.utc)
        db.execute(insert(RevokedToken).values(jti=claims["jti"], expires_at=expires)
                   .on_conflict_do_nothing(index_elements=["jti"]))
        # Housekeeping: expired tokens are rejected anyway, so their rows are dead weight.
        db.execute(delete(RevokedToken).where(RevokedToken.expires_at < datetime.now(timezone.utc)))
        db.commit()
    return {"status": "signed_out"}
