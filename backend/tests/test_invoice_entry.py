import base64
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.main import app
from app.models.business import Invoice, PurchaseOrder, Vendor
from app.services.invoice_identity import invoice_duplicate_key


@pytest.fixture
def client(monkeypatch):
    from app.api import invoices
    from app.models.identity import Company, User
    from tests.auth_helpers import headers, make_company, make_user

    # audit_events uses PostgreSQL JSONB; audit rows are covered by the PostgreSQL suite.
    monkeypatch.setattr(invoices, "record_audit_event", lambda *args, **kwargs: None)
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[Company.__table__, User.__table__, Vendor.__table__,
                                             PurchaseOrder.__table__, Invoice.__table__])
    with Session(engine) as session:
        member = make_user(session, "company", make_company(session))
        admin = make_user(session, "admin")
        session.commit()
        app.dependency_overrides[get_db] = lambda: session
        try:
            client = TestClient(app, headers=headers(member))
            client.admin = headers(admin)
            yield client
        finally:
            app.dependency_overrides.pop(get_db, None)
    engine.dispose()


def test_invoice_endpoints_require_company_login(client):
    anonymous = {"Authorization": ""}
    assert client.get("/api/v1/invoices", headers=anonymous).status_code == 401
    assert client.post("/api/v1/invoices", json=numbered_invoice(), headers=anonymous).status_code == 401
    # Admins oversee invoices but do not submit them on a company's behalf.
    assert client.post("/api/v1/invoices", json=numbered_invoice(), headers=client.admin).status_code == 403
    assert client.post("/api/v1/invoices/extract-pdf", json={"content": "x"}, headers=client.admin).status_code == 403


def test_manual_entry_and_existing_po(client):
    response = client.post("/api/v1/invoices", json={"supplier_name": "Acme", "po_amount": "1000", "amount": "1150", "currency": "USD", "invoice_number": "INV-1", "invoice_date": "2026-11-01"})
    assert response.status_code == 201
    invoice = response.json()
    assert client.get(f"/api/v1/invoices/{invoice['id']}/validate").json()["valid"] is False
    orders = client.get("/api/v1/invoices/purchase-orders").json()
    assert orders[0]["vendor_name"] == "Acme"
    response = client.post("/api/v1/invoices", json={"purchase_order_id": orders[0]["id"], "amount": "1000", "currency": "USD", "invoice_number": "INV-2", "invoice_date": "2026-11-01"})
    assert response.status_code == 201
    assert client.get(f"/api/v1/invoices/{response.json()['id']}/validate").json()["valid"] is True
    assert len(client.get("/api/v1/invoices").json()) == 2


def test_invalid_manual_entry(client):
    assert client.post("/api/v1/invoices", json={"amount": "10"}).status_code == 422
    assert client.post("/api/v1/invoices", json={"supplier_name": " ", "po_amount": "10", "amount": "10"}).status_code == 422
    assert client.post("/api/v1/invoices", json={"supplier_name": "Acme", "po_amount": "10", "amount": "-1"}).status_code == 422


def numbered_invoice(**overrides):
    return {"supplier_name": "Acme Limited", "po_amount": "1000", "amount": "1150", "currency": "USD",
            "invoice_number": "INV-100", "invoice_date": "2026-11-01", "due_date": "2026-11-30", **overrides}


def test_identity_dates_saved_and_duplicate_blocked(client):
    original = client.post("/api/v1/invoices", json=numbered_invoice()).json()
    assert original["invoice_number"] == "INV-100"
    assert original["invoice_date"] == "2026-11-01"
    assert original["due_date"] == "2026-11-30"
    duplicate = client.post("/api/v1/invoices", json=numbered_invoice(supplier_name="  ACME   limited ", invoice_number=" inv-100 ", amount="900"))
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["invoice_id"] == original["id"]
    # Rejected submissions must not leave an extra PO or supplier behind.
    assert len(client.get("/api/v1/invoices/purchase-orders").json()) == 1
    assert len(client.get("/api/v1/invoices").json()) == 1
    existing_po = client.post("/api/v1/invoices", json={"purchase_order_id": original["purchase_order_id"], "invoice_number": "INV-100", "invoice_date": "2026-11-01", "amount": "1100"})
    assert existing_po.status_code == 409
    assert client.post("/api/v1/invoices", json=numbered_invoice(invoice_number="INV-101")).status_code == 201
    assert client.post("/api/v1/invoices", json=numbered_invoice(supplier_name="Another supplier")).status_code == 201


@pytest.mark.parametrize("fields", [{"invoice_number": " "}, {"invoice_number": "X" * 101}, {"due_date": "2026-10-31"}, {"invoice_date": "not-a-date"}])
def test_identity_validation(client, fields):
    assert client.post("/api/v1/invoices", json=numbered_invoice(**fields)).status_code == 422


def test_identity_normalization():
    assert invoice_duplicate_key("ＡＣＭＥ  ltd", " inv-1 ") == invoice_duplicate_key("acme ltd", "INV-1")
    assert invoice_duplicate_key("Acme", "INV-1") != invoice_duplicate_key("Acme", "INV1")
    assert invoice_duplicate_key("Acme", None) is None


def test_pdf_identity_and_date_extraction(client):
    content = pdf_content("Invoice No: INV-2026-001 Invoice date: 2026-11-01 Due date: November 30, 2026 Invoice total: USD 1,150.00")
    result = client.post("/api/v1/invoices/extract-pdf", json={"content": content}).json()
    assert result["invoice_number"] == "INV-2026-001"
    assert result["invoice_date"] == "2026-11-01"
    assert result["due_date"] == "2026-11-30"
    result = client.post("/api/v1/invoices/extract-pdf", json={"content": pdf_content("Invoice total: USD 10.00 Invoice date: 01/02/2026")}).json()
    assert result["invoice_number"] is None
    assert result["invoice_date"] is None  # Never guess ambiguous day/month order.


def test_database_unique_constraint():
    from sqlalchemy.exc import IntegrityError
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[Vendor.__table__, PurchaseOrder.__table__, Invoice.__table__])
    with Session(engine) as session:
        vendor = Vendor(name="Acme", external_ref="acme")
        session.add(vendor)
        session.flush()
        po = PurchaseOrder(vendor_id=vendor.id, total_amount=1000, currency="USD")
        session.add(po)
        session.flush()
        fields = dict(vendor_id=vendor.id, purchase_order_id=po.id, amount=1000, currency="USD", invoice_number="INV-1", duplicate_key=invoice_duplicate_key("Acme", "INV-1"))
        session.add(Invoice(**fields))
        session.commit()
        session.add(Invoice(**fields))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
    engine.dispose()


def pdf_content(text=None):
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=400)
    if text:
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 12 Tf 10 300 Td ({text}) Tj ET".encode())
        page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return base64.b64encode(output.getvalue()).decode()


def test_pdf_extraction_review_only(client):
    response = client.post("/api/v1/invoices/extract-pdf", json={"content": pdf_content("Invoice total: USD 1,150.00")})
    assert response.status_code == 200
    assert response.json()["amount"] == "1150.00"
    assert response.json()["currency"] == "USD"
    assert client.get("/api/v1/invoices").json() == []


@pytest.mark.parametrize("content", ["invalid!", base64.b64encode(b"not a PDF").decode(), pdf_content(), base64.b64encode(b"%PDF-broken").decode()])
def test_bad_pdf_rejected(client, content):
    assert client.post("/api/v1/invoices/extract-pdf", json={"content": content}).status_code == 422


def test_pdf_limits_and_encryption(client):
    writer = PdfWriter()
    for _ in range(21):
        writer.add_blank_page(width=100, height=100)
    output = BytesIO()
    writer.write(output)
    assert client.post("/api/v1/invoices/extract-pdf", json={"content": base64.b64encode(output.getvalue()).decode()}).status_code == 422
    writer.encrypt("password")
    output = BytesIO()
    writer.write(output)
    assert client.post("/api/v1/invoices/extract-pdf", json={"content": base64.b64encode(output.getvalue()).decode()}).status_code == 422
    assert client.post("/api/v1/invoices/extract-pdf", json={"content": base64.b64encode(b"%PDF-" + b"0" * (5 * 1024 * 1024)).decode()}).status_code == 413
