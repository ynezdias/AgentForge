"""Development-only manager authentication for the local approval demo."""

import secrets
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.workflows import execution_response
from app.db.session import get_db
from app.models.workflow import ApprovalRequest, StepExecution, Workflow, WorkflowExecution
from app.schemas.workflow import WorkflowDefinition
from app.services.workflow_engine import execute_workflow


router = APIRouter(prefix="/api/v1/approvals", tags=["Approvals"])


class ApprovalDecision(BaseModel):
    decision: Literal["approve", "reject"]


def require_demo_manager(x_demo_manager_token: str | None = Header(default=None)):
    if x_demo_manager_token is None or not secrets.compare_digest(
        x_demo_manager_token.encode(), b"local-manager-demo"
    ):
        raise HTTPException(403, "A valid demo manager token is required")


@router.post("/{execution_id}", dependencies=[Depends(require_demo_manager)])
def decide_approval(
    execution_id: uuid.UUID, payload: ApprovalDecision, db: Session = Depends(get_db)
):
    execution = db.scalar(select(WorkflowExecution).where(
        WorkflowExecution.id == execution_id
    ).with_for_update())
    if execution is None:
        raise HTTPException(404, "Execution not found")
    approval = db.scalar(select(ApprovalRequest).where(
        ApprovalRequest.execution_id == execution_id
    ))
    if approval is None:
        raise HTTPException(404, "Approval request not found")
    if execution.status != "WAITING_APPROVAL" or approval.status != "PENDING":
        raise HTTPException(409, "Approval already processed")
    if approval.requested_role != "manager":
        raise HTTPException(403, "Unsupported approval role")

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
    approval.decided_by = "demo-manager"
    approval_step.status = "COMPLETED" if approved else "REJECTED"
    approval_step.result = {"decision": payload.decision, "decided_by": "demo-manager"}
    execution.context = {**dict(execution.context or {}), "approved": approved}
    execution.status = "RUNNING" if approved else "REJECTED"
    db.commit()
    if approved:
        execution = execute_workflow(db, execution, definition)
    return execution_response(db, execution)
