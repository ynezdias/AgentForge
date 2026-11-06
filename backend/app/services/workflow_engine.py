"""Synchronous local MVP; do not execute the same execution concurrently.

Steps and their cursor are committed together. There is no execution claiming or
durable resume job, so this does not provide crash-safe worker recovery.
"""

import uuid

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.business import Invoice, PurchaseOrder
from app.models.workflow import ApprovalRequest, StepExecution, WorkflowExecution
from app.schemas.workflow import WorkflowDefinition
from app.services.invoice_validation import validate_invoice


def execute_workflow(
    db: Session, execution: WorkflowExecution, definition: WorkflowDefinition
):
    if execution.status not in ("PENDING", "RUNNING"):
        return execution
    steps = definition.steps
    positions = {step.id: index for index, step in enumerate(steps)}
    context = dict(execution.context or {})
    cursor = execution.current_step
    try:
        execution.status = "RUNNING"
        db.commit()
        invoice = db.get(Invoice, uuid.UUID(execution.input_data["invoice_id"]))
        if invoice is None:
            raise ValueError("Invoice not found")

        while cursor < len(steps):
            step = steps[cursor]
            next_cursor = cursor + 1
            if step.type == "tool" and step.tool == "invoice.validate":
                po = db.get(PurchaseOrder, invoice.purchase_order_id)
                if po is None:
                    raise ValueError("Purchase order not found")
                result = jsonable_encoder(validate_invoice(invoice, po))
                context.update(result)
            elif step.type == "tool" and step.tool == "invoice.resolve":
                approval = db.scalar(select(ApprovalRequest).where(
                    ApprovalRequest.execution_id == execution.id
                ))
                if approval is None or approval.status != "APPROVED":
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
                db.commit()
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
            db.commit()
            cursor = next_cursor

        execution.status = "COMPLETED"
        db.commit()
    except Exception as exc:
        db.rollback()
        execution.status = "FAILED"
        execution.context = {**dict(execution.context or {}), "error": str(exc)}
        db.commit()
    db.refresh(execution)
    return execution
