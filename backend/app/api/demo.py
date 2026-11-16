"""Explicit setup action for the local portfolio workspace (admin only, never in production)."""
import os
import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.security import is_production
from app.db.session import get_db
from app.models.business import Invoice, PurchaseOrder, Vendor
from app.models.identity import Company, User
from app.models.workflow import Workflow, WorkflowExecution
from app.services.invoice_identity import invoice_duplicate_key

router = APIRouter(prefix="/api/v1/demo", tags=["Local demo"])

DEFAULT_DEMO_COMPANY = "DevForge"
# (vendor index, PO index, amount, invoice number, invoice date, due date)
SAMPLE_INVOICES = (
    (0, 0, "1000.00", "ACME-1001", date(2026, 10, 2), date(2026, 11, 1)),
    (0, 0, "1150.00", "ACME-1002", date(2026, 10, 9), date(2026, 11, 8)),
    (1, 1, "2500.00", "GTS-2001", date(2026, 10, 14), date(2026, 11, 13)),
    (0, 1, "2500.00", "ACME-1003", date(2026, 10, 20), date(2026, 11, 19)),
)


def demo_company(db: Session) -> Company:
    name = os.environ.get("DEMO_COMPANY_NAME", DEFAULT_DEMO_COMPANY).strip() or DEFAULT_DEMO_COMPANY
    company = db.scalar(select(Company).where(Company.name == name))
    if company is None:
        company = Company(name=name)
        db.add(company)
        db.flush()
    return company


def claim_unassigned_records(db: Session, company: Company) -> None:
    """Assign legacy rows created before multi-tenancy to the demo company."""
    for po in db.scalars(select(PurchaseOrder).where(PurchaseOrder.company_id.is_(None))):
        po.company_id = company.id
    for invoice in db.scalars(select(Invoice).where(Invoice.company_id.is_(None))):
        invoice.company_id = company.id
        if invoice.invoice_number:
            invoice.duplicate_key = invoice_duplicate_key(
                db.get(Vendor, invoice.vendor_id).name, invoice.invoice_number, company.id)
    db.flush()
    owners = {i.id: i.company_id for i in db.scalars(select(Invoice))}
    for execution in db.scalars(select(WorkflowExecution).where(WorkflowExecution.company_id.is_(None))):
        try:
            execution.company_id = owners.get(uuid.UUID(execution.input_data["invoice_id"]))
        except (KeyError, ValueError):
            continue


@router.post("/setup")
def setup_demo(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    if is_production() or os.environ.get("ENABLE_DEMO_SETUP", "false").lower() != "true":
        raise HTTPException(403, "Sample workspace setup is disabled")
    company = demo_company(db)
    vendors = []
    for name, ref in (("Acme Supplies", "VENDOR-001"), ("Global Tech Solutions", "VENDOR-002")):
        vendor = db.scalar(select(Vendor).where(Vendor.external_ref == ref))
        if vendor is None:
            vendor = Vendor(name=name, external_ref=ref)
            db.add(vendor)
            db.flush()
        vendors.append(vendor)
    orders = []
    for vendor, amount in zip(vendors, (Decimal("1000.00"), Decimal("2500.00"))):
        po = db.scalar(select(PurchaseOrder).where(
            PurchaseOrder.vendor_id == vendor.id, PurchaseOrder.total_amount == amount,
            PurchaseOrder.currency == "USD").order_by(PurchaseOrder.id).limit(1))
        if po is None:
            po = PurchaseOrder(vendor_id=vendor.id, total_amount=amount, currency="USD",
                               company_id=company.id)
            db.add(po)
            db.flush()
        orders.append(po)
    for vendor_i, po_i, amount, number, issued, due in SAMPLE_INVOICES:
        vendor, po = vendors[vendor_i], orders[po_i]
        existing = db.scalar(select(Invoice).where(
            Invoice.vendor_id == vendor.id, Invoice.purchase_order_id == po.id,
            Invoice.amount == Decimal(amount)).order_by(Invoice.id).limit(1))
        if existing is None:
            existing = Invoice(vendor_id=vendor.id, purchase_order_id=po.id,
                               amount=Decimal(amount), currency="USD", status="pending",
                               company_id=company.id)
            db.add(existing)
        if existing.invoice_number is None and (existing.company_id in (None, company.id)):
            existing.company_id = company.id
            existing.invoice_number, existing.invoice_date, existing.due_date = number, issued, due
            existing.duplicate_key = invoice_duplicate_key(vendor.name, number, company.id)
        db.flush()
    claim_unassigned_records(db, company)
    for use_ai in (False, True):
        name = "AI Invoice Exception Resolution" if use_ai else "Invoice Exception Review"
        if db.scalar(select(Workflow).where(Workflow.name == name)) is not None:
            continue
        steps = [
            {"id": "validate_invoice", "type": "tool", "tool": "invoice.validate"},
            {"id": "check_exception", "type": "condition", "field": "valid",
             "operator": "equals", "value": False,
             "on_true": "investigate_exception" if use_ai else "request_manager_approval",
             "on_false": "__end__"},
        ]
        if use_ai:
            steps.append({"id": "investigate_exception", "type": "tool", "tool": "invoice.investigate"})
        steps.extend([
            {"id": "request_manager_approval", "type": "approval", "role": "manager"},
            {"id": "record_resolution", "type": "tool", "tool": "invoice.resolve"},
        ])
        db.add(Workflow(name=name, definition={"name": name, "steps": steps}))
    db.commit()
    return {"status": "ready", "company": company.name}
