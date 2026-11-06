"""Local PostgreSQL tests; every test rolls back its data."""

import os
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import engine, get_db
from app.main import app
from app.models.business import Invoice, PurchaseOrder, Vendor
from app.models.workflow import ApprovalRequest, WorkflowExecution


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1", reason="Requires local migrated PostgreSQL"
)

DEFINITION = {
    "name": "Invoice Exception Approval",
    "steps": [
        {"id": "validate_invoice", "type": "tool", "tool": "invoice.validate"},
        {"id": "check_discrepancy", "type": "condition", "field": "valid",
         "operator": "equals", "value": False,
         "on_true": "request_approval", "on_false": "__end__"},
        {"id": "request_approval", "type": "approval", "role": "manager"},
        {"id": "apply_resolution", "type": "tool", "tool": "invoice.resolve"},
    ],
}
MANAGER = {"x-demo-manager-token": "local-manager-demo"}


@pytest.fixture
def demo():
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            with Session(bind=connection, join_transaction_mode="create_savepoint") as db:
                def override_db():
                    yield db

                app.dependency_overrides[get_db] = override_db
                try:
                    vendor = Vendor(name="Approval test", external_ref=str(uuid4()))
                    db.add(vendor)
                    db.flush()
                    po = PurchaseOrder(vendor_id=vendor.id, total_amount=Decimal("1000"))
                    db.add(po)
                    db.flush()
                    invoices = [Invoice(vendor_id=vendor.id, purchase_order_id=po.id,
                                        amount=Decimal(amount))
                                for amount in ("1000", "1150")]
                    db.add_all(invoices)
                    db.commit()
                    with TestClient(app) as client:
                        yield client, db, invoices
                finally:
                    app.dependency_overrides.pop(get_db, None)
        finally:
            transaction.rollback()


def start(client, invoice, definition=DEFINITION):
    response = client.post("/api/v1/workflows", json=definition)
    assert response.status_code == 201
    url = f'/api/v1/workflows/{response.json()["id"]}/execute'
    headers = {"idempotency-key": str(uuid4())}
    payload = {"invoice_id": str(invoice.id)}
    response = client.post(url, headers=headers, json=payload)
    assert response.status_code == 200
    return response.json(), url, headers, payload


def test_valid_invoice_ends_without_approval(demo):
    client, db, invoices = demo
    execution, _, _, _ = start(client, invoices[0])
    assert execution["status"] == "COMPLETED"
    assert execution["current_step"] == 4
    assert len(execution["steps"]) == 2
    assert db.scalar(select(ApprovalRequest).where(
        ApprovalRequest.execution_id == UUID(execution["execution_id"])
    )) is None
    db.refresh(invoices[0])
    assert invoices[0].status == "pending"


@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_approval_decision_and_duplicate_prevention(demo, decision):
    client, db, invoices = demo
    invoice = invoices[1]
    execution, url, headers, payload = start(client, invoice)
    execution_id = execution["execution_id"]
    assert execution["status"] == "WAITING_APPROVAL"
    assert execution["current_step"] == 3
    assert invoice.status == "pending"
    assert client.post(url, headers=headers, json=payload).json() == execution

    for auth in ({}, {"x-demo-manager-token": "wrong"}):
        denied = client.post(f"/api/v1/approvals/{execution_id}", headers=auth,
                             json={"decision": decision})
        assert denied.status_code == 403
    db.refresh(db.get(WorkflowExecution, UUID(execution_id)))
    assert db.get(WorkflowExecution, UUID(execution_id)).status == "WAITING_APPROVAL"

    decided = client.post(f"/api/v1/approvals/{execution_id}", headers=MANAGER,
                          json={"decision": decision})
    assert decided.status_code == 200
    result = decided.json()
    assert result["status"] == ("COMPLETED" if decision == "approve" else "REJECTED")
    assert result["current_step"] == (4 if decision == "approve" else 3)
    db.refresh(invoice)
    assert invoice.status == ("review_approved" if decision == "approve" else "pending")
    assert len(result["steps"]) == (4 if decision == "approve" else 3)
    approval = db.scalar(select(ApprovalRequest).where(
        ApprovalRequest.execution_id == UUID(execution_id)
    ))
    assert approval.status == ("APPROVED" if decision == "approve" else "REJECTED")
    assert approval.decided_by == "demo-manager"
    duplicate = client.post(f"/api/v1/approvals/{execution_id}", headers=MANAGER,
                            json={"decision": decision})
    assert duplicate.status_code == 409
    assert client.post(url, headers=headers, json=payload).json() == result
    assert client.get(f"/api/v1/workflows/executions/{execution_id}").json() == result


def test_resolution_cannot_bypass_approval(demo):
    client, db, invoices = demo
    execution, _, _, _ = start(client, invoices[1], {
        "name": "No approval", "steps": [
            {"id": "resolve", "type": "tool", "tool": "invoice.resolve"},
        ],
    })
    assert execution["status"] == "FAILED"
    assert execution["current_step"] == 0
    assert "requires manager approval" in execution["context"]["error"]
    assert execution["steps"] == []
    db.refresh(invoices[1])
    assert invoices[1].status == "pending"


def test_missing_condition_input_fails_without_resolution(demo):
    client, db, invoices = demo
    execution, _, _, _ = start(client, invoices[1], {
        "name": "Missing context", "steps": [
            {"id": "check", "type": "condition", "field": "valid",
             "operator": "equals", "value": False,
             "on_true": "__end__", "on_false": "__end__"},
        ],
    })
    assert execution["status"] == "FAILED"
    assert "unavailable" in execution["context"]["error"]
    assert execution["current_step"] == 0
