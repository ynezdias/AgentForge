"""Synchronous execution; callers must not run the same execution concurrently."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.business import Invoice, PurchaseOrder
from app.models.workflow import StepExecution, Workflow, WorkflowExecution
from app.schemas.workflow import WorkflowDefinition
from app.services.invoice_validation import validate_invoice


def execute_workflow(db: Session, execution: WorkflowExecution):
    if execution.status != "PENDING":
        return execution

    context = dict(execution.context or {})
    try:
        workflow = db.get(Workflow, execution.workflow_id)
        if workflow is None:
            raise ValueError("Workflow not found")
        definition = WorkflowDefinition.model_validate(workflow.definition)
        execution.status = "RUNNING"
        db.commit()

        for step in definition.steps:
            if step.type == "tool" and step.tool == "invoice.validate":
                invoice = db.get(Invoice, UUID(execution.input_data["invoice_id"]))
                if invoice is None:
                    raise ValueError("Invoice not found")
                po = db.get(PurchaseOrder, invoice.purchase_order_id)
                if po is None:
                    raise ValueError("Purchase order not found")
                validation = validate_invoice(invoice, po)
                result = {
                    "valid": validation["valid"],
                    "issues": validation["issues"],
                    "discrepancy_percentage": str(validation["discrepancy_percentage"]),
                }
                context.update(result)
            elif step.type == "condition":
                if step.field not in context:
                    raise ValueError(f"Condition field is unavailable: {step.field}")
                actual = context[step.field]
                result = {
                    "matched": actual == step.value,
                    "actual": actual,
                    "expected": step.value,
                }
                context["condition_matched"] = result["matched"]
            else:
                raise ValueError("Unsupported step type or tool")

            db.add(StepExecution(
                execution_id=execution.id,
                step_id=step.id,
                status="COMPLETED",
                result=result,
            ))
            execution.context = context.copy()
            db.commit()

        execution.status = "COMPLETED"
        db.commit()
    except Exception as exc:
        db.rollback()
        execution.status = "FAILED"
        execution.context = {**context, "error": str(exc)}
        db.commit()

    db.refresh(execution)
    return execution
