"""Verify duplicate requests and database protection on migrated PostgreSQL."""
import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.invoices import InvoiceCreate, create_invoice
from app.db.session import engine
from app.models.business import Invoice, PurchaseOrder, Vendor

pytestmark = pytest.mark.skipif(os.environ.get("RUN_DB_TESTS") != "1", reason="Requires migrated PostgreSQL")


def test_simultaneous_duplicate_submissions():
    token = str(uuid4())
    with Session(engine) as db:
        vendor = Vendor(name=f"Concurrency test {token}", external_ref=token)
        db.add(vendor)
        db.flush()
        po = PurchaseOrder(vendor_id=vendor.id, total_amount=1000, currency="USD")
        db.add(po)
        db.commit()
        vendor_id, po_id = vendor.id, po.id
    try:
        payload = InvoiceCreate(purchase_order_id=po_id, invoice_number="INV-1", invoice_date="2026-11-01", amount="1000", currency="USD")
        def submit(_):
            with Session(engine) as db:
                try:
                    return (201, str(create_invoice(payload, db).id))
                except HTTPException as exc:
                    return (exc.status_code, exc.detail["invoice_id"])
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(submit, range(2)))
        assert sorted(status for status, _ in results) == [201, 409]
        assert results[0][1] == results[1][1]
        with Session(engine) as db:
            assert len(db.scalars(select(Invoice).where(Invoice.vendor_id == vendor_id)).all()) == 1
    finally:
        with Session(engine) as db:
            db.execute(delete(Invoice).where(Invoice.vendor_id == vendor_id))
            db.execute(delete(PurchaseOrder).where(PurchaseOrder.id == po_id))
            db.execute(delete(Vendor).where(Vendor.id == vendor_id))
            db.commit()
