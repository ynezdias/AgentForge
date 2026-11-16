"""Admin oversight: decision overrides, reopening, and cross-company monitoring.

Overrides never edit the original ApprovalRequest. Each one appends a
DecisionOverride row (admin, time, original, new, reason) plus an audit event.
"""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from app.api.approvals import lock_execution
from app.api.deps import get_current_user, require_admin
from app.api.workflows import execution_response, start_execution
from app.db.session import get_db
from app.models.audit import AuditEvent
from app.models.business import Invoice
from app.models.governance import DecisionOverride
from app.models.identity import Company, User
from app.models.workflow import ApprovalRequest, Workflow, WorkflowExecution
from app.schemas.workflow import WorkflowDefinition
from app.services.audit import record_audit_event
from app.services.decisions import effective_decision
from app.services.recovery import recover_interrupted_runs
from app.services.workflow_engine import execute_workflow

router = APIRouter(prefix="/api/v1/admin", tags=["Admin oversight"])
activity_router = APIRouter(prefix="/api/v1/activity", tags=["Activity"])


class OverrideRequest(BaseModel):
    decision: Literal["approve", "reject"]
    reason: str = Field(min_length=10, max_length=1000)


class ReopenRequest(BaseModel):
    reason: str = Field(min_length=10, max_length=1000)


@router.post("/executions/{execution_id}/override")
def override_decision(execution_id: uuid.UUID, payload: OverrideRequest,
                      db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    execution = lock_execution(db, admin, execution_id)
    approval = db.scalar(select(ApprovalRequest).where(ApprovalRequest.execution_id == execution_id))
    if approval is None or approval.status == "PENDING":
        raise HTTPException(409, "There is no recorded decision to override; decide the approval instead")
    if execution.status not in ("COMPLETED", "REJECTED"):
        raise HTTPException(409, f"Executions in status {execution.status} cannot be overridden")
    original = effective_decision(db, approval)
    new = "APPROVED" if payload.decision == "approve" else "REJECTED"
    if original == new:
        raise HTTPException(409, f"The effective decision is already {original}")
    workflow = db.get(Workflow, execution.workflow_id)
    definition = WorkflowDefinition.model_validate(workflow.definition)
    invoice = db.get(Invoice, uuid.UUID(execution.input_data["invoice_id"]))

    override = DecisionOverride(execution_id=execution.id, approval_request_id=approval.id,
                                admin_user_id=admin.id, original_decision=original,
                                new_decision=new, reason=payload.reason.strip())
    db.add(override)
    db.flush()
    audit = dict(actor=admin, company_id=execution.company_id)
    record_audit_event(db, execution.id, "DECISION_OVERRIDDEN", {
        "override_id": override.id, "original_decision": original, "new_decision": new,
        "reason": override.reason, "original_decided_by": approval.decided_by,
    }, **audit)
    previous_status = execution.status
    resume = False
    execution.context = {**dict(execution.context or {}), "approved": new == "APPROVED"}
    if new == "REJECTED":
        execution.status = "REJECTED"
        invoice.status = "review_rejected"
    elif execution.current_step >= len(definition.steps):
        # Resolution already ran under an earlier approval; restore its outcome.
        execution.status = "COMPLETED"
        invoice.status = "review_approved"
    else:
        # Rejected before resolution ran: resume so the resolve step executes.
        execution.status = "RUNNING"
        resume = True
    record_audit_event(db, execution.id, "EXECUTION_STATE_CHANGED", {
        "from": previous_status, "to": execution.status, "via": "admin_override",
    }, **audit)
    db.commit()
    if resume:
        execution = execute_workflow(db, execution, definition)
    return execution_response(db, execution)


@router.post("/executions/{execution_id}/reopen")
def reopen(execution_id: uuid.UUID, payload: ReopenRequest,
           db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Start a fresh run for the same invoice; the original run stays untouched.

    The idempotency key is derived from the source execution, so a repeated
    reopen returns the same new run instead of creating another.
    """
    execution = lock_execution(db, admin, execution_id)
    if execution.status not in ("COMPLETED", "REJECTED", "FAILED"):
        raise HTTPException(409, "Only finished executions can be reopened")
    key = f"reopen:{execution.id}"
    existing = db.scalar(select(WorkflowExecution).where(WorkflowExecution.idempotency_key == key))
    if existing is not None:
        db.rollback()
        return execution_response(db, existing)
    invoice = db.get(Invoice, uuid.UUID(execution.input_data["invoice_id"]))
    invoice.status = "pending"
    record_audit_event(db, execution.id, "EXCEPTION_REOPENED", {
        "reason": payload.reason.strip(),
    }, actor=admin, company_id=execution.company_id, invoice_id=invoice.id)
    db.commit()
    new = start_execution(db, execution.workflow_id,
                          {"invoice_id": str(invoice.id), "reopened_from": str(execution.id)},
                          key, execution.company_id, admin)
    return execution_response(db, new)


@router.post("/recover-interrupted")
def recover_interrupted(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Mark abandoned runs (stuck after a crash or restart) as failed and retryable."""
    return {"recovered": recover_interrupted_runs(db, admin)}


@router.get("/overview")
def overview(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    by_status = dict(db.execute(select(WorkflowExecution.status, func.count())
                                .group_by(WorkflowExecution.status)).all())
    return {
        "companies": db.scalar(select(func.count()).select_from(Company)),
        "invoices": db.scalar(select(func.count()).select_from(Invoice)),
        "executions_by_status": by_status,
        "pending_approvals": by_status.get("WAITING_APPROVAL", 0),
        "escalated_pending": db.scalar(select(func.count()).select_from(WorkflowExecution).where(
            WorkflowExecution.escalated_at.is_not(None),
            WorkflowExecution.status == "WAITING_APPROVAL")),
        "overrides": db.scalar(select(func.count()).select_from(DecisionOverride)),
    }


@router.get("/companies")
def companies(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    rows = db.scalars(select(Company).order_by(Company.name)).all()
    invoice_counts = dict(db.execute(select(Invoice.company_id, func.count())
                                     .group_by(Invoice.company_id)).all())
    pending = dict(db.execute(select(WorkflowExecution.company_id, func.count()).where(
        WorkflowExecution.status == "WAITING_APPROVAL").group_by(WorkflowExecution.company_id)).all())
    users = dict(db.execute(select(User.company_id, func.count()).group_by(User.company_id)).all())
    return [{"id": c.id, "name": c.name, "created_at": c.created_at,
             "invoices": invoice_counts.get(c.id, 0), "pending_approvals": pending.get(c.id, 0),
             "users": users.get(c.id, 0)} for c in rows]


@router.get("/overrides")
def list_overrides(db: Session = Depends(get_db), admin: User = Depends(require_admin),
                   limit: int = Query(100, ge=1, le=200)):
    rows = db.execute(select(DecisionOverride, User.email).join(
        User, User.id == DecisionOverride.admin_user_id
    ).order_by(DecisionOverride.created_at.desc()).limit(limit)).all()
    return [{"id": o.id, "execution_id": o.execution_id, "admin_email": email,
             "original_decision": o.original_decision, "new_decision": o.new_decision,
             "reason": o.reason, "created_at": o.created_at} for o, email in rows]


@activity_router.get("")
def activity(db: Session = Depends(get_db), user: User = Depends(get_current_user),
             limit: int = Query(50, ge=1, le=200)):
    """Recent audit events: all companies for admins, own company otherwise."""
    execution = aliased(WorkflowExecution)
    company_col = func.coalesce(AuditEvent.company_id, execution.company_id)
    statement = (select(AuditEvent, User.email, Company.name)
                 .outerjoin(execution, execution.id == AuditEvent.execution_id)
                 .outerjoin(User, User.id == AuditEvent.actor_user_id)
                 .outerjoin(Company, Company.id == company_col))
    if user.role != "admin":
        statement = statement.where(company_col == user.company_id)
    rows = db.execute(statement.order_by(AuditEvent.created_at.desc(), AuditEvent.id)
                      .limit(limit)).all()
    return [{"id": event.id, "event_type": event.event_type, "execution_id": event.execution_id,
             "invoice_id": event.invoice_id, "actor_email": email, "company_name": company,
             "payload": event.payload, "created_at": event.created_at}
            for event, email, company in rows]
