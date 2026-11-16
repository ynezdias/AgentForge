"""Authentication and tenant-scoping dependencies shared by every router.

Company users only ever see rows whose company_id matches their own. Other
tenants' records return 404 rather than 403 so their existence is not revealed.
"""

import uuid

import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import AuthConfigurationError, decode_access_token, is_production
from app.db.session import get_db
from app.models.business import Invoice
from app.models.identity import RevokedToken, User
from app.models.workflow import WorkflowExecution

UNAUTHORIZED = HTTPException(401, "Sign in to continue", headers={"WWW-Authenticate": "Bearer"})


def get_current_user(authorization: str | None = Header(default=None),
                     db: Session = Depends(get_db)) -> User:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise UNAUTHORIZED
    try:
        claims = decode_access_token(token)
        user_id = uuid.UUID(claims["sub"])
    except AuthConfigurationError:
        raise HTTPException(503, "Authentication is not configured on the server") from None
    except (jwt.InvalidTokenError, ValueError, KeyError):
        raise UNAUTHORIZED from None
    if db.get(RevokedToken, claims["jti"]) is not None:
        raise UNAUTHORIZED
    user = db.get(User, user_id)
    if (user is None or not user.is_active or user.token_version != claims["ver"]
            or user.role != claims["role"] or (user.is_demo and is_production())):
        raise UNAUTHORIZED
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(403, "Admin access is required")
    return user


def require_company(user: User = Depends(get_current_user)) -> User:
    if user.role != "company":
        raise HTTPException(403, "This action is only available in the company portal")
    return user


def scoped(statement, column, user: User):
    """Restrict a SELECT to the user's company unless the user is an admin."""
    return statement if user.role == "admin" else statement.where(column == user.company_id)


def visible_invoice(db: Session, user: User, invoice_id: uuid.UUID) -> Invoice:
    invoice = db.get(Invoice, invoice_id)
    if invoice is None or (user.role != "admin" and invoice.company_id != user.company_id):
        raise HTTPException(404, "Invoice not found")
    return invoice


def visible_execution(db: Session, user: User, execution_id: uuid.UUID,
                      for_update: bool = False) -> WorkflowExecution:
    statement = select(WorkflowExecution).where(WorkflowExecution.id == execution_id)
    if for_update:
        statement = statement.with_for_update()
    execution = db.scalar(statement)
    if execution is None or (user.role != "admin" and execution.company_id != user.company_id):
        raise HTTPException(404, "Execution not found")
    return execution
