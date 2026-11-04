import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.business import Invoice, PurchaseOrder
from app.services.invoice_validation import validate_invoice


router = APIRouter(prefix="/api/v1/invoices", tags=["Invoices"])


class InvoiceCreate(BaseModel):
    vendor_id: uuid.UUID
    purchase_order_id: uuid.UUID
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")


class InvoiceResponse(InvoiceCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str


@router.post("", response_model=InvoiceResponse, status_code=201)
def create_invoice(payload: InvoiceCreate, db: Session = Depends(get_db)):
    po = db.get(PurchaseOrder, payload.purchase_order_id)

    if not po:
        raise HTTPException(404, "Purchase order not found")

    invoice = Invoice(**payload.model_dump())

    db.add(invoice)
    db.commit()
    db.refresh(invoice)

    return invoice


@router.get("", response_model=list[InvoiceResponse])
def list_invoices(db: Session = Depends(get_db)):
    from sqlalchemy import select

    return db.scalars(select(Invoice).limit(100)).all()


@router.get("/{invoice_id}/validate")
def check_invoice(invoice_id: uuid.UUID, db: Session = Depends(get_db)):
    invoice = db.get(Invoice, invoice_id)

    if not invoice:
        raise HTTPException(404, "Invoice not found")

    po = db.get(PurchaseOrder, invoice.purchase_order_id)

    if not po:
        raise HTTPException(404, "Purchase order not found")

    return validate_invoice(invoice, po)