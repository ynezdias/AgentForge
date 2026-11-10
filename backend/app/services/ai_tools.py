from fastapi.encoders import jsonable_encoder

from app.schemas.investigation import InvestigationResult
from app.services.investigation_agent import investigation_graph
from app.services.invoice_validation import validate_invoice


def investigate_invoice_tool(invoice, purchase_order):
    validation = jsonable_encoder(validate_invoice(invoice, purchase_order))
    if validation["valid"]:
        return {"skipped": True, "reason": "No invoice exception detected"}

    facts = {
        "invoice_id": str(invoice.id),
        "invoice_amount": str(invoice.amount),
        "invoice_currency": invoice.currency,
        "invoice_vendor_id": str(invoice.vendor_id),
        "purchase_order_amount": str(purchase_order.total_amount),
        "purchase_order_currency": purchase_order.currency,
        "purchase_order_vendor_id": str(purchase_order.vendor_id),
        "validation": validation,
        "policy_threshold_percentage": "5",
    }
    try:
        output = investigation_graph.invoke({"invoice_facts": facts})
        recommendation = InvestigationResult.model_validate(output["investigation"])
    except Exception:
        # Provider exceptions can include credentials or request data. The
        # workflow persists errors, so expose only a safe message here.
        raise RuntimeError("AI investigation failed") from None
    return {
        "skipped": False,
        "facts": facts,
        "recommendation": recommendation.model_dump(mode="json"),
    }
