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
from app.models.audit import AuditEvent
from app.models.investigation import InvoiceInvestigation
from app.services import ai_tools


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


AI_DEFINITION = {
    "name": "AI Invoice Exception Resolution",
    "steps": [
        {"id": "validate", "type": "tool", "tool": "invoice.validate"},
        {"id": "check", "type": "condition", "field": "valid",
         "operator": "equals", "value": False,
         "on_true": "investigate", "on_false": "__end__"},
        {"id": "investigate", "type": "tool", "tool": "invoice.investigate"},
        {"id": "approval", "type": "approval", "role": "manager"},
        {"id": "resolve", "type": "tool", "tool": "invoice.resolve"},
    ],
}


@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_ai_workflow_persistence_and_audit(demo, monkeypatch, decision):
    client, db, invoices = demo
    calls = []
    recommendation = {
        "summary": "15% discrepancy", "risk_level": "HIGH",
        "recommended_action": "REQUEST_CORRECTION", "reasoning": "Exceeds tolerance",
        "requires_human_approval": True,
    }

    class FakeGraph:
        def invoke(self, state):
            calls.append(state)
            return {"investigation": recommendation}

    monkeypatch.setattr(ai_tools, "investigation_graph", FakeGraph())
    execution, url, headers, payload = start(client, invoices[1], AI_DEFINITION)
    execution_id = UUID(execution["execution_id"])
    assert execution["status"] == "WAITING_APPROVAL"
    assert execution["current_step"] == 4
    assert execution["context"]["ai_recommendation"] == recommendation
    row = db.scalar(select(InvoiceInvestigation).where(
        InvoiceInvestigation.invoice_id == invoices[1].id
    ))
    assert row.result["execution_id"] == str(execution_id)
    assert row.result["facts"]["validation"]["discrepancy_percentage"] == 15.0
    assert row.result["recommendation"] == recommendation

    def events():
        return list(db.scalars(select(AuditEvent).where(
            AuditEvent.execution_id == execution_id
        ).order_by(AuditEvent.created_at)))

    before = events()
    assert all(event.created_at is not None for event in before)
    assert [event.payload["to"] for event in before
            if event.event_type == "EXECUTION_STATE_CHANGED"] == [
                "PENDING", "RUNNING", "WAITING_APPROVAL"
            ]
    assert any(event.event_type == "STEP_COMPLETED"
               and event.payload["step_id"] == "investigate" for event in before)
    assert client.post(url, headers=headers, json=payload).json() == execution
    assert len(events()) == len(before)
    approved = client.post(f"/api/v1/approvals/{execution_id}", headers=MANAGER,
                           json={"decision": decision})
    assert approved.status_code == 200
    assert approved.json()["status"] == ("COMPLETED" if decision == "approve" else "REJECTED")
    db.refresh(invoices[1])
    assert invoices[1].status == ("review_approved" if decision == "approve" else "pending")
    assert invoices[1].amount == Decimal("1150.00")
    history = events()
    decisions = [event for event in history if event.event_type == "APPROVAL_DECIDED"]
    assert len(decisions) == 1
    assert decisions[0].payload["decision"] == decision
    assert decisions[0].payload["scope"] == "workflow review-status action"
    assert history[-1].payload["to"] == approved.json()["status"]
    assert client.post(f"/api/v1/approvals/{execution_id}", headers=MANAGER,
                       json={"decision": decision}).status_code == 409
    assert len(events()) == len(history)
    assert len(calls) == 1


def test_valid_ai_workflow_bypasses_investigation(demo, monkeypatch):
    client, db, invoices = demo

    class NoCalls:
        def invoke(self, state):
            pytest.fail("Valid invoice must bypass investigation")

    monkeypatch.setattr(ai_tools, "investigation_graph", NoCalls())
    execution, _, _, _ = start(client, invoices[0], AI_DEFINITION)
    assert execution["status"] == "COMPLETED"
    assert len(execution["steps"]) == 2
    assert db.scalar(select(InvoiceInvestigation).where(
        InvoiceInvestigation.invoice_id == invoices[0].id
    )) is None


def test_ai_failure_records_failure_without_investigation(demo, monkeypatch):
    client, db, invoices = demo

    class FailedGraph:
        def invoke(self, state):
            raise RuntimeError("private-provider-secret")

    monkeypatch.setattr(ai_tools, "investigation_graph", FailedGraph())
    execution, _, _, _ = start(client, invoices[1], AI_DEFINITION)
    assert execution["status"] == "FAILED"
    assert execution["current_step"] == 2
    assert execution["context"]["error"] == "AI investigation failed"
    assert len(execution["steps"]) == 2
    assert db.scalar(select(InvoiceInvestigation).where(
        InvoiceInvestigation.invoice_id == invoices[1].id
    )) is None
    history = db.scalars(select(AuditEvent).where(
        AuditEvent.execution_id == UUID(execution["execution_id"])
    )).all()
    assert any(event.payload.get("to") == "FAILED" for event in history)
    assert "private-provider-secret" not in str([event.payload for event in history])
    assert invoices[1].status == "pending"


def test_investigation_and_step_roll_back_if_audit_write_fails(demo, monkeypatch):
    from app.services import workflow_engine

    client, db, invoices = demo

    class FakeGraph:
        def invoke(self, state):
            return {"investigation": {
                "summary": "15% discrepancy", "risk_level": "HIGH",
                "recommended_action": "REQUEST_CORRECTION", "reasoning": "Outside tolerance",
                "requires_human_approval": True,
            }}

    original = workflow_engine.record_audit_event

    def fail_investigation_audit(db, execution_id, event_type, payload):
        if event_type == "STEP_COMPLETED" and payload.get("step_id") == "investigate":
            raise RuntimeError("Simulated audit write failure")
        return original(db, execution_id, event_type, payload)

    monkeypatch.setattr(ai_tools, "investigation_graph", FakeGraph())
    monkeypatch.setattr(workflow_engine, "record_audit_event", fail_investigation_audit)
    execution, _, _, _ = start(client, invoices[1], AI_DEFINITION)
    assert execution["status"] == "FAILED"
    assert execution["current_step"] == 2
    assert len(execution["steps"]) == 2
    assert "ai_recommendation" not in execution["context"]
    assert db.scalar(select(InvoiceInvestigation).where(
        InvoiceInvestigation.invoice_id == invoices[1].id
    )) is None
    history = db.scalars(select(AuditEvent).where(
        AuditEvent.execution_id == UUID(execution["execution_id"])
    )).all()
    assert not any(event.payload.get("step_id") == "investigate" for event in history)
    assert any(event.payload.get("to") == "FAILED" for event in history)


@pytest.mark.parametrize("different_input", [False, True])
def test_idempotency_unique_constraint_race(demo, monkeypatch, different_input):
    client, db, invoices = demo
    execution, url, headers, payload = start(client, invoices[1])
    original_scalar = db.scalar
    calls = 0

    def miss_initial_lookup(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            # Simulate the initial lookup racing with a committed insertion.
            return None
        return original_scalar(*args, **kwargs)

    monkeypatch.setattr(db, "scalar", miss_initial_lookup)
    if different_input:
        payload = {"invoice_id": str(invoices[0].id)}
    replay = client.post(url, headers=headers, json=payload)
    assert replay.status_code == (409 if different_input else 200)
    if not different_input:
        assert replay.json() == execution


def test_engine_cannot_advance_locked_execution(demo):
    from app.models.workflow import Workflow
    from app.schemas.workflow import WorkflowDefinition
    from app.services.execution_lock import acquire_execution_lock
    from app.services.workflow_engine import execute_workflow

    _, db, invoices = demo
    definition = WorkflowDefinition.model_validate({"name": "Locked execution", "steps": [
        {"id": "validate", "type": "tool", "tool": "invoice.validate"},
    ]})
    workflow = Workflow(name=definition.name, definition=definition.model_dump())
    db.add(workflow)
    db.flush()
    execution = WorkflowExecution(workflow_id=workflow.id,
                                  input_data={"invoice_id": str(invoices[0].id)},
                                  idempotency_key=str(uuid4()))
    db.add(execution)
    db.commit()
    with Session(engine) as other:
        assert acquire_execution_lock(other, execution.id)
        blocked = execute_workflow(db, execution, definition)
        assert blocked.status == "PENDING"
        assert blocked.current_step == 0
        other.rollback()
    completed = execute_workflow(db, execution, definition)
    assert completed.status == "COMPLETED"
    assert completed.current_step == 1
