"""Synchronous local MVP with transaction locks around each state transition.

Steps and their cursor are committed together. There is no execution claiming or
durable resume job, so this does not provide crash-safe worker recovery.
"""

import uuid
import logging

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.ai_config import ai_settings
from app.models.business import Invoice, PurchaseOrder
from app.models.investigation import InvoiceInvestigation
from app.models.workflow import ApprovalRequest, StepExecution, WorkflowExecution
from app.schemas.workflow import WorkflowDefinition
from app.services.invoice_validation import validate_invoice
from app.services.ai_tools import investigate_invoice_tool
from app.services.audit import record_audit_event
from app.services.decisions import effective_decision
from app.services.workflow_errors import describe_failure, failure_context
from app.services.execution_lock import acquire_execution_lock

logger = logging.getLogger(__name__)


def log_state(execution, event, step_id=None):
    fields = {"execution_id": execution.id, "status": execution.status, "event": event}
    if step_id is not None:
        fields["step_id"] = step_id
    logger.info(event, extra=fields)

def execute_workflow(
    db: Session, execution: WorkflowExecution, definition: WorkflowDefinition
):
    if not acquire_execution_lock(db, execution.id):
        db.refresh(execution)
        return execution
    db.refresh(execution)
    if execution.status not in ("PENDING", "RUNNING"):
        return execution
    steps = definition.steps
    positions = {step.id: index for index, step in enumerate(steps)}
    context = dict(execution.context or {})
    cursor = execution.current_step
    try:
        previous_status = execution.status
        execution.status = "RUNNING"
        if previous_status != execution.status:
            record_audit_event(db, execution.id, "EXECUTION_STATE_CHANGED", {
                "from": previous_status, "to": execution.status,
            })
        db.commit()
        log_state(execution, "workflow_execution_started")
        while True:
            # A step commit releases the transaction advisory lock. Reacquire
            # and reload before reading the cursor or invoking business logic.
            if not acquire_execution_lock(db, execution.id):
                db.refresh(execution)
                return execution
            db.refresh(execution)
            if execution.status != "RUNNING":
                return execution
            cursor = execution.current_step
            context = dict(execution.context or {})
            if cursor >= len(steps):
                break
            invoice = db.get(Invoice, uuid.UUID(execution.input_data["invoice_id"]))
            if invoice is None:
                raise ValueError("Invoice not found")
            step = steps[cursor]
            next_cursor = cursor + 1
            if step.type == "tool" and step.tool == "invoice.validate":
                po = db.get(PurchaseOrder, invoice.purchase_order_id)
                if po is None:
                    raise ValueError("Purchase order not found")
                result = jsonable_encoder(validate_invoice(invoice, po))
                context.update(result)
            elif step.type == "tool" and step.tool == "invoice.investigate":
                po = db.get(PurchaseOrder, invoice.purchase_order_id)
                if po is None:
                    raise ValueError("Purchase order not found")
                result = investigate_invoice_tool(invoice, po)
                context["investigation"] = result
                if not result["skipped"]:
                    context["ai_recommendation"] = result["recommendation"]
                    db.add(InvoiceInvestigation(
                        invoice_id=invoice.id, model_name=ai_settings.gemini_model,
                        result={"execution_id": str(execution.id),
                                "facts": result["facts"],
                                "recommendation": result["recommendation"]},
                    ))
            elif step.type == "tool" and step.tool == "invoice.resolve":
                approval = db.scalar(select(ApprovalRequest).where(
                    ApprovalRequest.execution_id == execution.id
                ))
                # Honour admin overrides; the original approval row is never edited.
                if approval is None or effective_decision(db, approval) != "APPROVED":
                    raise ValueError("Invoice resolution requires manager approval")
                invoice.status = "review_approved"
                result = {"invoice_id": str(invoice.id), "status": invoice.status}
                context["invoice_status"] = invoice.status
            elif step.type == "condition":
                if step.field not in context:
                    raise ValueError(f"Condition field is unavailable: {step.field}")
                actual = context[step.field]
                matched = actual == step.value
                target = step.on_true if matched else step.on_false
                next_cursor = len(steps) if target == "__end__" else positions[target]
                result = {"matched": matched, "actual": actual,
                          "expected": step.value, "next_step": target}
                context["condition_matched"] = matched
            elif step.type == "approval":
                db.add(ApprovalRequest(execution_id=execution.id, requested_role=step.role))
                db.add(StepExecution(
                    execution_id=execution.id, step_id=step.id,
                    status="WAITING_APPROVAL", result={"role": step.role},
                ))
                execution.current_step = next_cursor
                execution.context = jsonable_encoder(context)
                execution.status = "WAITING_APPROVAL"
                record_audit_event(db, execution.id, "STEP_WAITING_APPROVAL", {
                    "step_id": step.id, "role": step.role,
                })
                record_audit_event(db, execution.id, "EXECUTION_STATE_CHANGED", {
                    "from": "RUNNING", "to": "WAITING_APPROVAL",
                })
                db.commit()
                log_state(execution, "workflow_waiting_approval", step.id)
                db.refresh(execution)
                return execution
            else:
                raise ValueError("Unsupported step type or tool")

            db.add(StepExecution(
                execution_id=execution.id, step_id=step.id,
                status="COMPLETED", result=jsonable_encoder(result),
            ))
            execution.context = jsonable_encoder(context)
            execution.current_step = next_cursor
            record_audit_event(db, execution.id, "STEP_COMPLETED", {
                "step_id": step.id, "result": result, "current_step": next_cursor,
            })
            db.commit()
            log_state(execution, "workflow_step_completed", step.id)
            cursor = next_cursor

        execution.status = "COMPLETED"
        record_audit_event(db, execution.id, "EXECUTION_STATE_CHANGED", {
            "from": "RUNNING", "to": "COMPLETED",
        })
        db.commit()
        log_state(execution, "workflow_execution_completed")
    except Exception as exc:
        db.rollback()
        # Rollback released the lock too. Do not overwrite progress made by
        # another caller after the failed transaction ended.
        if not acquire_execution_lock(db, execution.id):
            db.refresh(execution)
            return execution
        db.refresh(execution)
        if execution.status not in ("PENDING", "RUNNING") or execution.current_step != cursor:
            return execution
        previous_status = execution.status
        code, message = describe_failure(exc)
        failed_step = steps[cursor].id if cursor < len(steps) else None
        execution.status = "FAILED"
        execution.context = {**dict(execution.context or {}),
                             **failure_context(code, message, failed_step)}
        record_audit_event(db, execution.id, "EXECUTION_STATE_CHANGED", {
            "from": previous_status, "to": "FAILED", "error": message, "error_code": code,
            "failed_step": failed_step, "current_step": execution.current_step,
        })
        db.commit()
        log_state(execution, "workflow_execution_failed")
    db.refresh(execution)
    return execution
