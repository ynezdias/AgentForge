"""Recovering failed and interrupted workflow runs.

Retry resumes at the failed step: completed steps are never re-run, and the
failed step's partial work was rolled back with its transaction, so resuming
cannot duplicate an investigation or a decision.

A run is "interrupted" when it is still PENDING/RUNNING long after its last
update and no process holds its advisory lock. The engine holds that lock for
the whole of each step (including the AI call), so a free lock on a stale run
means nobody is working on it any more, for example after a crash or restart.
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.workflow import Workflow, WorkflowExecution
from app.services.audit import record_audit_event
from app.services.execution_lock import acquire_execution_lock
from app.services.workflow_errors import FAILURE_CODES, failure_context

logger = logging.getLogger(__name__)

STALE_AFTER = timedelta(minutes=10)
MAX_MANUAL_RETRIES = 5
FAILURE_KEYS = ("error", "error_code", "failed_step", "retryable")


def is_stale(execution: WorkflowExecution, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    return execution.status in ("PENDING", "RUNNING") and execution.updated_at < now - STALE_AFTER


def _step_id(db: Session, execution: WorkflowExecution) -> str | None:
    workflow = db.get(Workflow, execution.workflow_id)
    steps = (workflow.definition or {}).get("steps", []) if workflow else []
    return steps[execution.current_step]["id"] if execution.current_step < len(steps) else None


def mark_interrupted(db: Session, execution: WorkflowExecution, actor=None) -> None:
    """Caller must hold the execution's advisory lock."""
    previous = execution.status
    execution.status = "FAILED"
    execution.context = {**dict(execution.context or {}),
                         **failure_context("INTERRUPTED", FAILURE_CODES["INTERRUPTED"][1], _step_id(db, execution))}
    record_audit_event(db, execution.id, "EXECUTION_STATE_CHANGED", {
        "from": previous, "to": "FAILED", "error_code": "INTERRUPTED",
        "current_step": execution.current_step,
    }, actor=actor, company_id=execution.company_id)


def recover_interrupted_runs(db: Session, actor=None) -> int:
    """Mark abandoned runs as failed-and-retryable. Safe to run from several processes."""
    cutoff = datetime.now(timezone.utc) - STALE_AFTER
    candidates = db.scalars(select(WorkflowExecution.id).where(
        WorkflowExecution.status.in_(("PENDING", "RUNNING")),
        WorkflowExecution.updated_at < cutoff)).all()
    recovered = 0
    for execution_id in candidates:
        if not acquire_execution_lock(db, execution_id):
            db.rollback()  # Someone is actively running it.
            continue
        execution = db.scalar(select(WorkflowExecution).where(
            WorkflowExecution.id == execution_id).with_for_update())
        if execution is not None and is_stale(execution):
            mark_interrupted(db, execution, actor)
            recovered += 1
        db.commit()
    if recovered:
        logger.info("interrupted_runs_recovered", extra={"count": recovered})
    return recovered


def retry_state(execution: WorkflowExecution) -> dict:
    """What the UI needs to offer (or explain the absence of) a retry."""
    context = execution.context or {}
    failed = execution.status == "FAILED"
    retryable = failed and context.get("retryable", True) is not False
    return {"attempt_count": execution.attempt_count,
            "max_retries": MAX_MANUAL_RETRIES,
            "can_retry": retryable and execution.attempt_count < MAX_MANUAL_RETRIES,
            "stale": is_stale(execution)}


def prepare_retry(db: Session, execution: WorkflowExecution, actor) -> None:
    """Validate and move a FAILED run back to RUNNING. Caller holds the lock and commits."""
    if is_stale(execution):
        mark_interrupted(db, execution, actor)
    if execution.status != "FAILED":
        raise HTTPException(409, "Only failed runs can be retried")
    context = dict(execution.context or {})
    if context.get("retryable", True) is False:
        raise HTTPException(409, "Retrying cannot change this failure. Fix the workflow or data, or ask an admin to reopen it.")
    if execution.attempt_count >= MAX_MANUAL_RETRIES:
        raise HTTPException(409, f"This run has been retried {MAX_MANUAL_RETRIES} times. An admin can reopen it as a new run.")
    execution.attempt_count += 1
    record_audit_event(db, execution.id, "EXECUTION_RETRIED", {
        "attempt": execution.attempt_count, "previous_error_code": context.get("error_code"),
        "failed_step": context.get("failed_step"),
    }, actor=actor, company_id=execution.company_id)
    record_audit_event(db, execution.id, "EXECUTION_STATE_CHANGED", {
        "from": "FAILED", "to": "RUNNING", "via": "retry",
    }, actor=actor, company_id=execution.company_id)
    execution.context = {k: v for k, v in context.items() if k not in FAILURE_KEYS}
    execution.status = "RUNNING"
