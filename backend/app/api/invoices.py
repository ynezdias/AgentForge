import uuid
from decimal import Decimal
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models.business import Invoice, PurchaseOrder, Vendor
from app.services.invoice_validation import validate_invoice
from app.services.invoice_identity import invoice_duplicate_key, normalize_identity


router = APIRouter(prefix="/api/v1/invoices", tags=["Invoices"])


class InvoiceCreate(BaseModel):
    invoice_number: str = Field(min_length=1, max_length=100)
    invoice_date: date
    due_date: date | None = None
    vendor_id: uuid.UUID | None = None
    purchase_order_id: uuid.UUID | None = None
    supplier_name: str | None = Field(default=None, min_length=1, max_length=200)
    po_amount: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")

    @field_validator("invoice_number")
    @classmethod
    def clean_number(cls, value):
        if value is not None and not value.strip():
            raise ValueError("Invoice number cannot be blank")
        return value.strip() if value else value

    @model_validator(mode="after")
    def check_dates(self):
        if self.invoice_date and self.due_date and self.due_date < self.invoice_date:
            raise ValueError("Due date cannot be before invoice date")
        return self


class InvoiceResponse(InvoiceCreate):
    model_config = ConfigDict(from_attributes=True)
    invoice_number: str | None = None
    invoice_date: date | None = None

    id: uuid.UUID
    status: str
    vendor_name: str | None = None
    purchase_order_amount: Decimal | None = None
    purchase_order_currency: str | None = None
    validation: dict | None = None


@router.post("", response_model=InvoiceResponse, status_code=201)
def create_invoice(payload: InvoiceCreate, db: Session = Depends(get_db)):
    if payload.purchase_order_id:
        po = db.get(PurchaseOrder, payload.purchase_order_id)
        if not po:
            raise HTTPException(404, "Purchase order not found")
        vendor_id = payload.vendor_id or po.vendor_id
        vendor = db.get(Vendor, vendor_id)
        if not vendor:
            raise HTTPException(404, "Supplier not found")
    else:
        if not payload.supplier_name or not payload.supplier_name.strip() or payload.po_amount is None:
            raise HTTPException(422, "Enter a supplier name and purchase order total, or select an existing purchase order")
        vendor = next((v for v in db.scalars(select(Vendor)).all()
                       if normalize_identity(v.name) == normalize_identity(payload.supplier_name)), None)
        if vendor is None:
            vendor = Vendor(name=payload.supplier_name.strip(), external_ref=f"manual-{uuid.uuid4()}")
            db.add(vendor)
            db.flush()
        vendor_id = vendor.id
        po = PurchaseOrder(vendor_id=vendor_id, total_amount=payload.po_amount, currency=payload.currency)
        db.add(po)
        db.flush()
    key = invoice_duplicate_key(vendor.name, payload.invoice_number)
    def reject_duplicate(existing):
        db.rollback()
        raise HTTPException(409, {"code": "DUPLICATE_INVOICE", "message": "An invoice with this supplier and invoice number already exists. Open it instead of submitting again.",
                                  "invoice_id": str(existing.id)})

    if key:
        existing = db.scalar(select(Invoice).where(Invoice.duplicate_key == key))
        if existing:
            reject_duplicate(existing)
    invoice = Invoice(vendor_id=vendor_id, purchase_order_id=po.id,
                      amount=payload.amount, currency=payload.currency,
                      invoice_number=payload.invoice_number, invoice_date=payload.invoice_date,
                      due_date=payload.due_date, duplicate_key=key)

    db.add(invoice)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(Invoice).where(Invoice.duplicate_key == key)) if key else None
        if existing:
            reject_duplicate(existing)
        raise
    db.refresh(invoice)

    return invoice


@router.get("/purchase-orders")
def purchase_orders(db: Session = Depends(get_db)):
    from sqlalchemy import select
    orders = db.scalars(select(PurchaseOrder).options(selectinload(PurchaseOrder.vendor)).order_by(PurchaseOrder.id)).all()
    return [{"id": str(po.id), "vendor_name": po.vendor.name, "amount": str(po.total_amount),
             "currency": po.currency} for po in orders]


class PDFUpload(BaseModel):
    content: str = Field(max_length=7_000_000)


@router.post("/extract-pdf")
def extract_pdf(payload: PDFUpload):
    from app.services.invoice_pdf import extract_invoice_pdf
    return extract_invoice_pdf(payload.content)


@router.get("", response_model=list[InvoiceResponse])
def list_invoices(db: Session = Depends(get_db)):
    from sqlalchemy import select

    invoices = db.scalars(select(Invoice).options(
        selectinload(Invoice.vendor), selectinload(Invoice.purchase_order)
    ).order_by(Invoice.id).limit(100)).all()
    results = []
    for invoice in invoices:
        result = InvoiceResponse.model_validate(invoice).model_dump()
        po = invoice.purchase_order
        result.update(vendor_name=invoice.vendor.name,
                      purchase_order_amount=po.total_amount,
                      purchase_order_currency=po.currency)
        try:
            result["validation"] = validate_invoice(invoice, po)
        except ValueError:
            result["validation"] = {"valid": False, "issues": ["INVALID_PURCHASE_ORDER_AMOUNT"],
                                    "discrepancy_percentage": None}
        results.append(result)
    return results


@router.get("/{invoice_id}/validate")
def check_invoice(invoice_id: uuid.UUID, db: Session = Depends(get_db)):
    invoice = db.get(Invoice, invoice_id)

    if not invoice:
        raise HTTPException(404, "Invoice not found")

    po = db.get(PurchaseOrder, invoice.purchase_order_id)

    if not po:
        raise HTTPException(404, "Purchase order not found")

    return validate_invoice(invoice, po)
