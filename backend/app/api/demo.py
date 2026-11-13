"""Explicit setup action for the local portfolio workspace."""
import os
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.approvals import require_demo_manager
from app.db.session import get_db
from app.models.business import Invoice, PurchaseOrder, Vendor
from app.models.workflow import Workflow

router = APIRouter(prefix="/api/v1/demo", tags=["Local demo"])


@router.post("/setup", dependencies=[Depends(require_demo_manager)])
def setup_demo(db: Session = Depends(get_db)):
    if os.environ.get("ENABLE_DEMO_SETUP", "false").lower() != "true":
        raise HTTPException(403, "Sample workspace setup is disabled")
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
            PurchaseOrder.currency == "USD"))
        if po is None:
            po = PurchaseOrder(vendor_id=vendor.id, total_amount=amount, currency="USD")
            db.add(po)
            db.flush()
        orders.append(po)
    for vendor, po, amount in ((vendors[0], orders[0], "1000.00"),
                               (vendors[0], orders[0], "1150.00"),
                               (vendors[1], orders[1], "2500.00"),
                               (vendors[0], orders[1], "2500.00")):
        existing = db.scalar(select(Invoice).where(
            Invoice.vendor_id == vendor.id, Invoice.purchase_order_id == po.id,
            Invoice.amount == Decimal(amount)))
        if existing is None:
            db.add(Invoice(vendor_id=vendor.id, purchase_order_id=po.id,
                           amount=Decimal(amount), currency="USD", status="pending"))
            db.flush()
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
    return {"status": "ready"}
