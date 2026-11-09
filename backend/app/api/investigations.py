import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.core.ai_config import ai_settings
from app.db.session import get_db
from app.models.business import Invoice, PurchaseOrder
from app.models.investigation import InvoiceInvestigation
from app.schemas.investigation import InvestigationResult
from app.services.investigation_agent import investigation_graph
from app.services.invoice_validation import validate_invoice


router = APIRouter(prefix="/api/v1/investigations", tags=["AI Investigations"])


@router.post("/{invoice_id}")
def investigate_invoice(invoice_id: uuid.UUID, db: Session = Depends(get_db)):
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(404, "Invoice not found")
    po = db.get(PurchaseOrder, invoice.purchase_order_id)
    if po is None:
        raise HTTPException(404, "Purchase order not found")
    if not ai_settings.google_api_key.get_secret_value().strip():
        raise HTTPException(503, "Configure GOOGLE_API_KEY in backend/.env to use investigations")
    try:
        validation = validate_invoice(invoice, po)
    except ValueError:
        raise HTTPException(422, "Purchase order amount must be positive")

    # Send only typed facts and deterministic validation, never database access.
    facts = jsonable_encoder({
        "invoice_id": invoice.id,
        "invoice_amount": str(invoice.amount),
        "invoice_currency": invoice.currency,
        "purchase_order_amount": str(po.total_amount),
        "purchase_order_currency": po.currency,
        "vendor_matches": invoice.vendor_id == po.vendor_id,
        "validation": validation,
    })
    try:
        state = investigation_graph.invoke({"invoice_facts": facts})
        result = InvestigationResult.model_validate(state["investigation"])
    except Exception:
        # Provider errors may contain credentials or request data; keep them private.
        raise HTTPException(502, "AI investigation failed; no result was saved") from None

    investigation = InvoiceInvestigation(
        invoice_id=invoice.id,
        model_name=ai_settings.gemini_model,
        result=result.model_dump(mode="json"),
    )
    db.add(investigation)
    db.commit()
    db.refresh(investigation)
    return {
        "id": investigation.id,
        "invoice_id": investigation.invoice_id,
        "model_name": investigation.model_name,
        "result": investigation.result,
        "created_at": investigation.created_at,
    }
