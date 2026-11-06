import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.business import Invoice
from app.models.workflow import Workflow, WorkflowExecution, StepExecution
from app.schemas.workflow import WorkflowDefinition
from app.services.workflow_engine import execute_workflow


router = APIRouter(prefix="/api/v1/workflows", tags=["Workflows"])


class ExecuteRequest(BaseModel):
    invoice_id: uuid.UUID


@router.post("", status_code=201)
def create_workflow(payload: WorkflowDefinition, db: Session = Depends(get_db)):
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
    return {
        "execution_id": execution.id,
        "workflow_id": execution.workflow_id,
        "status": execution.status,
        "current_step": execution.current_step,
        "context": execution.context,
        "steps": [
            {"step_id": step.step_id, "status": step.status, "result": step.result}
            for step in sorted(steps, key=lambda step: order.get(step.step_id, 0))
        ],
    }


@router.post("/{workflow_id}/execute")
def run_workflow(
    workflow_id: uuid.UUID,
    payload: ExecuteRequest,
    idempotency_key: str = Header(min_length=1, max_length=200),
    db: Session = Depends(get_db),
):
    input_data = payload.model_dump(mode="json")

    def replay(existing):
        if existing.workflow_id != workflow_id or existing.input_data != input_data:
            raise HTTPException(409, "Idempotency key was used for a different request")
        return execution_response(db, existing)

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
    if db.get(Invoice, payload.invoice_id) is None:
        raise HTTPException(404, "Invoice not found")

    execution = WorkflowExecution(
        workflow_id=workflow_id,
        input_data=input_data,
        idempotency_key=idempotency_key,
    )
    db.add(execution)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(WorkflowExecution).where(
            WorkflowExecution.idempotency_key == idempotency_key
        ))
        if existing is None:
            raise
        return replay(existing)
    db.refresh(execution)
    return execution_response(db, execute_workflow(db, execution, definition))


@router.get("/executions/{execution_id}")
def get_execution(execution_id: uuid.UUID, db: Session = Depends(get_db)):
    execution = db.get(WorkflowExecution, execution_id)
    if execution is None:
        raise HTTPException(404, "Execution not found")
    return execution_response(db, execution)
