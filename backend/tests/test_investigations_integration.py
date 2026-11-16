"""Opt-in PostgreSQL persistence tests; Gemini is mocked, all data rolled back."""

import os
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import investigations
from app.core.ai_config import ai_settings
from app.db.session import engine, get_db
from app.main import app
from app.models.business import Invoice, PurchaseOrder, Vendor
from app.models.investigation import InvoiceInvestigation
from tests.auth_helpers import headers as auth_headers, make_company, make_user


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1", reason="Requires local migrated PostgreSQL"
)


@pytest.fixture
def demo(monkeypatch):
    monkeypatch.setattr(ai_settings, "google_api_key", SecretStr("fake-test-key"))
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            with Session(bind=connection, join_transaction_mode="create_savepoint") as db:
                def override_db():
                    yield db

                app.dependency_overrides[get_db] = override_db
                try:
                    company = make_company(db)
                    member = make_user(db, "company", company)
                    outsider = make_user(db, "company", make_company(db))
                    vendor = Vendor(name="Investigation test", external_ref=str(uuid4()))
                    db.add(vendor)
                    db.flush()
                    po = PurchaseOrder(vendor_id=vendor.id, total_amount=Decimal("1000"))
                    db.add(po)
                    db.flush()
                    invoice = Invoice(vendor_id=vendor.id, purchase_order_id=po.id,
                                      amount=Decimal("1150"), company_id=company.id)
                    db.add(invoice)
                    db.commit()
                    with TestClient(app, headers=auth_headers(member)) as client:
                        client.outsider = auth_headers(outsider)
                        yield client, db, invoice
                finally:
                    app.dependency_overrides.pop(get_db, None)
        finally:
            transaction.rollback()


def test_investigation_saved_without_changing_invoice(demo, monkeypatch):
    client, db, invoice = demo
    result = {"summary": "15% discrepancy", "risk_level": "HIGH",
              "recommended_action": "REQUEST_CORRECTION", "reasoning": "Outside tolerance",
              "requires_human_approval": True}
    graph = MagicMock()
    graph.invoke.return_value = {"investigation": result}
    monkeypatch.setattr(investigations, "investigation_graph", graph)
    response = client.post(f"/api/v1/investigations/{invoice.id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["result"] == result
    row = db.get(InvoiceInvestigation, UUID(payload["id"]))
    assert row.result == result
    assert row.invoice_id == invoice.id
    assert row.created_at is not None
    assert row.model_name == ai_settings.gemini_model
    facts = graph.invoke.call_args.args[0]["invoice_facts"]
    assert facts["validation"]["discrepancy_percentage"] == 15.0
    assert facts["validation"]["issues"] == ["AMOUNT_DISCREPANCY"]
    assert set(facts) == {"invoice_id", "invoice_amount", "invoice_currency",
                          "purchase_order_amount", "purchase_order_currency",
                          "vendor_matches", "validation"}
    db.refresh(invoice)
    assert invoice.status == "pending"
    assert invoice.amount == Decimal("1150.00")


@pytest.mark.parametrize("failure", ["provider", "invalid_result"])
def test_failed_investigation_not_saved(demo, monkeypatch, failure):
    client, db, invoice = demo
    graph = MagicMock()
    if failure == "provider":
        graph.invoke.side_effect = RuntimeError("private provider credentials")
    else:
        graph.invoke.return_value = {"investigation": {"summary": "incomplete"}}
    monkeypatch.setattr(investigations, "investigation_graph", graph)
    response = client.post(f"/api/v1/investigations/{invoice.id}")
    assert response.status_code == 502
    assert "private" not in response.text
    assert db.scalar(select(InvoiceInvestigation).where(
        InvoiceInvestigation.invoice_id == invoice.id
    )) is None


def test_missing_key_returns_configuration_error(demo, monkeypatch):
    client, db, invoice = demo
    monkeypatch.setattr(ai_settings, "google_api_key", SecretStr(""))
    graph = MagicMock()
    monkeypatch.setattr(investigations, "investigation_graph", graph)
    response = client.post(f"/api/v1/investigations/{invoice.id}")
    assert response.status_code == 503
    graph.invoke.assert_not_called()
    assert client.get("/health").status_code == 200


def test_missing_invoice_returns_404(demo, monkeypatch):
    client, _, _ = demo
    graph = MagicMock()
    monkeypatch.setattr(investigations, "investigation_graph", graph)
    assert client.post(f"/api/v1/investigations/{uuid4()}").status_code == 404
    graph.invoke.assert_not_called()


def test_other_company_cannot_investigate(demo, monkeypatch):
    client, _, invoice = demo
    graph = MagicMock()
    monkeypatch.setattr(investigations, "investigation_graph", graph)
    assert client.post(f"/api/v1/investigations/{invoice.id}",
                       headers=client.outsider).status_code == 404
    assert client.post(f"/api/v1/investigations/{invoice.id}",
                       headers={"Authorization": ""}).status_code == 401
    graph.invoke.assert_not_called()
