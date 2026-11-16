"""Human approval decisions and escalation.

Company users decide their own company's pending approvals. An escalated
execution can only be decided by an admin. Admins may decide any approval.
"""

import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, visible_execution
from app.api.workflows import execution_response
from app.db.session import get_db
from app.models.business import Invoice
from app.models.identity import User
from app.models.workflow import ApprovalRequest, StepExecution, Workflow
from app.schemas.workflow import WorkflowDefinition
from app.services.workflow_engine import execute_workflow
from app.services.audit import record_audit_event
from app.services.execution_lock import acquire_execution_lock


router = APIRouter(prefix="/api/v1/approvals", tags=["Approvals"])


class ApprovalDecision(BaseModel):
    decision: Literal["approve", "reject"]


class EscalationRequest(BaseModel):
    reason: str = Field(min_length=10, max_length=1000)


def lock_execution(db: Session, user: User, execution_id: uuid.UUID):
    if not acquire_execution_lock(db, execution_id):
        raise HTTPException(409, "Execution is busy; try again later")
    return visible_execution(db, user, execution_id, for_update=True)


@router.post("/{execution_id}")
def decide_approval(
    execution_id: uuid.UUID, payload: ApprovalDecision, db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    execution = lock_execution(db, user, execution_id)
    approval = db.scalar(select(ApprovalRequest).where(
        ApprovalRequest.execution_id == execution_id
    ))
    if approval is None:
        raise HTTPException(404, "Approval request not found")
    if execution.status != "WAITING_APPROVAL" or approval.status != "PENDING":
        raise HTTPException(409, "Approval already processed")
    if approval.requested_role != "manager":
        raise HTTPException(403, "Unsupported approval role")
    if execution.escalated_at is not None and user.role != "admin":
        raise HTTPException(403, "This exception was escalated and needs an admin decision")

    workflow = db.get(Workflow, execution.workflow_id)
    if workflow is None:
        raise HTTPException(404, "Workflow not found")
    try:
        definition = WorkflowDefinition.model_validate(workflow.definition)
    except ValueError:
        raise HTTPException(422, "Stored workflow does not match the current workflow contract")
    approval_step = db.scalar(select(StepExecution).where(
        StepExecution.execution_id == execution_id,
        StepExecution.status == "WAITING_APPROVAL",
    ))
    if approval_step is None:
        raise HTTPException(409, "Waiting approval step not found")

    approved = payload.decision == "approve"
    approval.status = "APPROVED" if approved else "REJECTED"
    approval.decided_by = user.email
    approval.decided_by_user_id = user.id
    approval.decided_at = datetime.now(timezone.utc)
    approval_step.status = "COMPLETED" if approved else "REJECTED"
    approval_step.result = {"decision": payload.decision, "decided_by": user.email,
                            "decided_by_role": user.role}
    execution.context = {**dict(execution.context or {}), "approved": approved}
    execution.status = "RUNNING" if approved else "REJECTED"
    if not approved:
        invoice = db.get(Invoice, uuid.UUID(execution.input_data["invoice_id"]))
        if invoice is not None:
            invoice.status = "review_rejected"
    audit = dict(actor=user, company_id=execution.company_id)
    record_audit_event(db, execution.id, "APPROVAL_DECIDED", {
        "decision": payload.decision, "decided_by": approval.decided_by,
        "approval_id": approval.id,
        "scope": "workflow review-status action",
    }, **audit)
    record_audit_event(db, execution.id, "STEP_COMPLETED" if approved else "STEP_REJECTED", {
        "step_id": approval_step.step_id, "result": approval_step.result,
    }, **audit)
    record_audit_event(db, execution.id, "EXECUTION_STATE_CHANGED", {
        "from": "WAITING_APPROVAL", "to": execution.status,
    }, **audit)
    db.commit()
    if approved:
        execution = execute_workflow(db, execution, definition)
    return execution_response(db, execution)


@router.post("/{execution_id}/escalate")
def escalate(execution_id: uuid.UUID, payload: EscalationRequest,
             db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Route a pending decision to an admin. Either role may escalate."""
    execution = lock_execution(db, user, execution_id)
    if execution.status != "WAITING_APPROVAL":
        raise HTTPException(409, "Only exceptions waiting for approval can be escalated")
    if execution.escalated_at is not None:
        raise HTTPException(409, "Exception is already escalated")
    execution.escalated_at = datetime.now(timezone.utc)
    record_audit_event(db, execution.id, "EXCEPTION_ESCALATED", {
        "reason": payload.reason.strip(),
    }, actor=user, company_id=execution.company_id)
    db.commit()
    return execution_response(db, execution)
