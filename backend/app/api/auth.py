from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import (AuthConfigurationError, burn_password_check, create_access_token,
                               is_production, verify_password)
from app.db.session import get_db
from app.models.identity import Company, User

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


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(func.lower(User.email) == payload.email.strip().lower()))
    if user is None:
        burn_password_check(payload.password)
        raise INVALID
    if not verify_password(payload.password, user.password_hash):
        raise INVALID
    if not user.is_active or (user.is_demo and is_production()):
        raise INVALID
    if user.role != payload.portal:
        # Only reachable with the correct password, so this reveals nothing new.
        other = "Admin" if user.role == "admin" else "Company"
        raise HTTPException(403, f"This account signs in through the {other} portal")
    try:
        token, expires_at = create_access_token(user.id, user.role, user.token_version)
    except AuthConfigurationError:
        raise HTTPException(503, "Authentication is not configured on the server") from None
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    return {"access_token": token, "token_type": "bearer", "expires_at": expires_at,
            "user": user_profile(db, user)}


@router.get("/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return user_profile(db, user)
