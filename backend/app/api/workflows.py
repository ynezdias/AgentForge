import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin, scoped, visible_execution, visible_invoice
from app.db.session import get_db
from app.models.audit import AuditEvent
from app.models.governance import DecisionOverride
from app.models.identity import User
from app.models.workflow import ApprovalRequest, Workflow, WorkflowExecution, StepExecution
from app.schemas.workflow import WorkflowDefinition
from app.services.workflow_engine import execute_workflow
from app.services.audit import record_audit_event


router = APIRouter(prefix="/api/v1/workflows", tags=["Workflows"])


class ExecuteRequest(BaseModel):
    invoice_id: uuid.UUID


@router.get("")
def list_workflows(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    workflows = db.scalars(select(Workflow).order_by(Workflow.name, Workflow.id).limit(100)).all()
    return [{"id": workflow.id, "name": workflow.name, "version": workflow.version,
             "definition": workflow.definition}
            for workflow in workflows]


@router.get("/executions")
def list_executions(db: Session = Depends(get_db), user: User = Depends(get_current_user),
                    status: str | None = None, invoice_id: uuid.UUID | None = None,
                    escalated: bool | None = None, limit: int = Query(100, ge=1, le=100)):
    statement = scoped(select(WorkflowExecution), WorkflowExecution.company_id, user)
    if status:
        statement = statement.where(WorkflowExecution.status == status)
    if invoice_id:
        statement = statement.where(WorkflowExecution.input_data["invoice_id"].astext == str(invoice_id))
    if escalated is not None:
        column = WorkflowExecution.escalated_at
        statement = statement.where(column.is_not(None) if escalated else column.is_(None))
    executions = db.scalars(statement.order_by(WorkflowExecution.created_at.desc(), WorkflowExecution.id).limit(limit)).all()
    names = {w.id: w.name for w in db.scalars(select(Workflow).where(
        Workflow.id.in_({e.workflow_id for e in executions}))).all()} if executions else {}
    return [{"execution_id": execution.id, "workflow_id": execution.workflow_id,
             "workflow_name": names.get(execution.workflow_id, "Workflow"),
             "invoice_id": execution.input_data.get("invoice_id"),
             "company_id": execution.company_id, "escalated_at": execution.escalated_at,
             "status": execution.status, "created_at": execution.created_at,
             "current_step": execution.current_step, "context": execution.context}
            for execution in executions]


@router.post("", status_code=201)
def create_workflow(payload: WorkflowDefinition, db: Session = Depends(get_db),
                    user: User = Depends(require_admin)):
    workflow = Workflow(name=payload.name, definition=payload.model_dump())
    db.add(workflow)
    db.commit()
    db.refresh(workflow)
    return {"id": workflow.id, "name": workflow.name, "version": workflow.version}


def execution_response(db: Session, execution: WorkflowExecution):
    steps = db.scalars(select(StepExecution).where(
        StepExecution.execution_id == execution.id
    )).all()
    workflow = db.get(Workflow, execution.workflow_id)
    order = {
        step["id"]: index
        for index, step in enumerate(workflow.definition["steps"])
    } if workflow else {}
    approval = db.scalar(select(ApprovalRequest).where(ApprovalRequest.execution_id == execution.id))
    overrides = db.scalars(select(DecisionOverride).where(
        DecisionOverride.execution_id == execution.id
    ).order_by(DecisionOverride.created_at, DecisionOverride.id)).all()
    admins = {u.id: u.email for u in db.scalars(select(User).where(
        User.id.in_({o.admin_user_id for o in overrides}))).all()} if overrides else {}
    return {
        "execution_id": execution.id,
        "workflow_id": execution.workflow_id,
        "workflow_name": workflow.name if workflow else "Workflow",
        "invoice_id": execution.input_data.get("invoice_id"),
        "reopened_from": execution.input_data.get("reopened_from"),
        "company_id": execution.company_id,
        "escalated_at": execution.escalated_at,
        "created_at": execution.created_at,
        "total_steps": len(workflow.definition["steps"]) if workflow else 0,
        "status": execution.status,
        "current_step": execution.current_step,
        "context": execution.context,
        "approval": None if approval is None else {
            "status": approval.status, "decided_by": approval.decided_by,
            "decided_at": approval.decided_at,
            "effective_decision": overrides[-1].new_decision if overrides else approval.status,
        },
        "overrides": [{"id": o.id, "admin_email": admins.get(o.admin_user_id),
                       "original_decision": o.original_decision, "new_decision": o.new_decision,
                       "reason": o.reason, "created_at": o.created_at} for o in overrides],
        "steps": [
            {"step_id": step.step_id, "status": step.status, "result": step.result}
            for step in sorted(steps, key=lambda step: order.get(step.step_id, 0))
        ],
    }


def start_execution(db: Session, workflow_id: uuid.UUID, input_data: dict,
                    idempotency_key: str, company_id, actor: User):
    """Create and run an execution once per idempotency key.

    A repeated key with the same input returns the original execution instead
    of starting a second run; a repeated key with different input is a conflict.
    """
    def replay(existing):
        if existing.workflow_id != workflow_id or existing.input_data != input_data:
            raise HTTPException(409, "Idempotency key was used for a different request")
        return existing

    existing = db.scalar(select(WorkflowExecution).where(
        WorkflowExecution.idempotency_key == idempotency_key
    ))
    if existing:
        return replay(existing)
    workflow = db.get(Workflow, workflow_id)
    if workflow is None:
        raise HTTPException(404, "Workflow not found")
    try:
        definition = WorkflowDefinition.model_validate(workflow.definition)
    except ValueError:
        raise HTTPException(422, "Stored workflow does not match the current workflow contract")

    execution = WorkflowExecution(
        workflow_id=workflow_id,
        input_data=input_data,
        idempotency_key=idempotency_key,
        company_id=company_id,
    )
    db.add(execution)
    try:
        db.flush()
        record_audit_event(db, execution.id, "EXECUTION_STATE_CHANGED", {
            "from": None, "to": "PENDING",
        }, actor=actor, company_id=company_id,
            invoice_id=uuid.UUID(input_data["invoice_id"]))
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(WorkflowExecution).where(
            WorkflowExecution.idempotency_key == idempotency_key
        ))
        if existing is None:
            raise HTTPException(409, "Execution creation conflict") from None
        return replay(existing)
    db.refresh(execution)
    return execute_workflow(db, execution, definition)


@router.post("/{workflow_id}/execute")
def run_workflow(
    workflow_id: uuid.UUID,
    payload: ExecuteRequest,
    idempotency_key: str = Header(min_length=1, max_length=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    input_data = payload.model_dump(mode="json")
    # Replays are checked inside start_execution, but tenant visibility of the
    # invoice is checked first so a key cannot be used to probe other companies.
    invoice = visible_invoice(db, user, payload.invoice_id)
    execution = start_execution(db, workflow_id, input_data, idempotency_key,
                                invoice.company_id, user)
    if user.role != "admin" and execution.company_id != user.company_id:
        raise HTTPException(409, "Idempotency key was used for a different request")
    return execution_response(db, execution)


@router.get("/executions/{execution_id}")
def get_execution(execution_id: uuid.UUID, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    return execution_response(db, visible_execution(db, user, execution_id))


@router.get("/executions/{execution_id}/audit")
def get_execution_audit(execution_id: uuid.UUID, db: Session = Depends(get_db),
                        user: User = Depends(get_current_user)):
    visible_execution(db, user, execution_id)
    events = db.scalars(select(AuditEvent).where(AuditEvent.execution_id == execution_id)
                        .order_by(AuditEvent.created_at, AuditEvent.id)).all()
    return [{"id": event.id, "event_type": event.event_type, "payload": event.payload,
             "actor_user_id": event.actor_user_id, "created_at": event.created_at}
            for event in events]
