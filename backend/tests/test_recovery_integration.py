"""Retryable AI failures, manual retry from the failed step, and interrupted-run recovery."""

import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import engine, get_db
from app.main import app
from app.models.audit import AuditEvent
from app.models.business import Invoice, PurchaseOrder, Vendor
from app.models.investigation import InvoiceInvestigation
from app.models.workflow import StepExecution, WorkflowExecution
from app.services import ai_tools
from app.services.recovery import MAX_MANUAL_RETRIES, STALE_AFTER
from app.services.retry_policy import invoke_ai_with_retry
from tests.auth_helpers import headers, make_company, make_user

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1", reason="Requires local migrated PostgreSQL"
)

AI_DEFINITION = {"name": "AI review", "steps": [
    {"id": "validate", "type": "tool", "tool": "invoice.validate"},
    {"id": "check", "type": "condition", "field": "valid", "operator": "equals", "value": False,
     "on_true": "investigate", "on_false": "__end__"},
    {"id": "investigate", "type": "tool", "tool": "invoice.investigate"},
    {"id": "approval", "type": "approval", "role": "manager"},
    {"id": "resolve", "type": "tool", "tool": "invoice.resolve"},
]}
RECOMMENDATION = {"summary": "15% over", "risk_level": "HIGH", "recommended_action": "REQUEST_CORRECTION",
                  "reasoning": "Outside tolerance", "requires_human_approval": True}


def high_demand():
    from google.genai.errors import ServerError
    return ServerError(503, {"error": {"code": 503, "message": "high demand", "status": "UNAVAILABLE"}})


class Graph:
    """Fails with the given error for the first `failures` calls, then succeeds."""

    def __init__(self, failures, error=high_demand):
        self.failures, self.error, self.calls = failures, error, 0

    def invoke(self, state):
        self.calls += 1
        if self.calls <= self.failures:
            raise self.error()
        return {"investigation": RECOMMENDATION}


@pytest.fixture
def env(monkeypatch):
    # Real retry policy, without the real back-off delays.
    monkeypatch.setattr(ai_tools, "invoke_ai_with_retry", invoke_ai_with_retry.retry_with(sleep=lambda _: None))
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            with Session(bind=connection, join_transaction_mode="create_savepoint") as db:
                app.dependency_overrides[get_db] = lambda: db
                try:
                    company = make_company(db)
                    users = SimpleNamespace(member=make_user(db, "company", company), admin=make_user(db, "admin"),
                                            outsider=make_user(db, "company", make_company(db)))
                    vendor = Vendor(name="Recovery supplier", external_ref=str(uuid4()))
                    db.add(vendor)
                    db.flush()
                    po = PurchaseOrder(vendor_id=vendor.id, total_amount=Decimal("1000"), company_id=company.id)
                    db.add(po)
                    db.flush()
                    invoice = Invoice(vendor_id=vendor.id, purchase_order_id=po.id, amount=Decimal("1150"),
                                      company_id=company.id)
                    db.add(invoice)
                    db.commit()
                    with TestClient(app) as client:
                        yield SimpleNamespace(client=client, db=db, invoice=invoice, users=users,
                                              h={k: headers(v) for k, v in vars(users).items()})
                finally:
                    app.dependency_overrides.pop(get_db, None)
        finally:
            transaction.rollback()


def start(env, definition=AI_DEFINITION):
    workflow = env.client.post("/api/v1/workflows", json=definition, headers=env.h["admin"]).json()
    response = env.client.post(f"/api/v1/workflows/{workflow['id']}/execute", json={"invoice_id": str(env.invoice.id)},
                               headers={**env.h["member"], "idempotency-key": str(uuid4())})
    assert response.status_code == 200, response.text
    return response.json()


def retry(env, execution_id, who="member"):
    return env.client.post(f"/api/v1/workflows/executions/{execution_id}/retry", headers=env.h[who])


def test_transient_ai_failure_is_retried_automatically(env, monkeypatch):
    graph = Graph(failures=2)
    monkeypatch.setattr(ai_tools, "investigation_graph", graph)
    run = start(env)
    assert run["status"] == "WAITING_APPROVAL"
    assert graph.calls == 3


def test_persistent_outage_fails_retryably_then_manual_retry_resumes(env, monkeypatch):
    monkeypatch.setattr(ai_tools, "investigation_graph", Graph(failures=99))
    run = start(env)
    assert run["status"] == "FAILED"
    assert run["context"]["error_code"] == "AI_UNAVAILABLE"
    assert run["context"]["failed_step"] == "investigate"
    assert run["context"]["retryable"] is True
    assert run["retry"]["can_retry"] is True and run["retry"]["attempt_count"] == 0
    assert "high demand" not in str(run)  # Provider text never reaches the stored error.
    eid = UUID(run["execution_id"])

    # Another company cannot see or retry it; anonymous callers are rejected.
    assert retry(env, eid, "outsider").status_code == 404
    assert env.client.post(f"/api/v1/workflows/executions/{eid}/retry").status_code == 401

    graph = Graph(failures=0)
    monkeypatch.setattr(ai_tools, "investigation_graph", graph)
    resumed = retry(env, eid)
    assert resumed.status_code == 200
    body = resumed.json()
    assert body["status"] == "WAITING_APPROVAL"
    assert body["retry"]["attempt_count"] == 1
    assert "error" not in body["context"] and body["context"]["ai_recommendation"] == RECOMMENDATION
    assert graph.calls == 1
    # Completed steps were not re-run; exactly one investigation was saved.
    validate_rows = env.db.scalar(select(func.count()).select_from(StepExecution).where(
        StepExecution.execution_id == eid, StepExecution.step_id == "validate"))
    assert validate_rows == 1
    assert env.db.scalar(select(func.count()).select_from(InvoiceInvestigation).where(
        InvoiceInvestigation.invoice_id == env.invoice.id)) == 1
    retried = env.db.scalars(select(AuditEvent).where(
        AuditEvent.execution_id == eid, AuditEvent.event_type == "EXECUTION_RETRIED")).all()
    assert len(retried) == 1 and retried[0].actor_user_id == env.users.member.id
    assert retried[0].payload["previous_error_code"] == "AI_UNAVAILABLE"
    # A second click after it has moved on is refused, not run twice.
    assert retry(env, eid).status_code == 409


def test_invalid_ai_output_is_a_distinct_failure(env, monkeypatch):
    class BadOutput:
        def invoke(self, state):
            return {"investigation": {"summary": "incomplete"}}

    monkeypatch.setattr(ai_tools, "investigation_graph", BadOutput())
    run = start(env)
    assert run["context"]["error_code"] == "AI_FAILED"
    assert run["context"]["error"] == "AI investigation failed"


def test_business_rule_failure_is_not_retryable(env):
    run = start(env, {"name": "No approval", "steps": [{"id": "resolve", "type": "tool", "tool": "invoice.resolve"}]})
    assert run["context"]["error_code"] == "STEP_FAILED"
    assert run["retry"]["can_retry"] is False
    assert "Retrying cannot change this failure" in retry(env, run["execution_id"]).json()["detail"]


def test_retry_limit(env, monkeypatch):
    monkeypatch.setattr(ai_tools, "investigation_graph", Graph(failures=99))
    eid = UUID(start(env)["execution_id"])
    row = env.db.get(WorkflowExecution, eid)
    row.attempt_count = MAX_MANUAL_RETRIES
    env.db.commit()
    response = retry(env, eid)
    assert response.status_code == 409 and "admin can reopen" in response.json()["detail"]


def test_interrupted_run_is_recovered_and_resumable(env, monkeypatch):
    monkeypatch.setattr(ai_tools, "investigation_graph", Graph(failures=99))
    eid = UUID(start(env)["execution_id"])
    # Simulate a crash mid-step: still RUNNING, last touched long ago.
    row = env.db.get(WorkflowExecution, eid)
    row.status = "RUNNING"
    row.context = {k: v for k, v in row.context.items() if k not in ("error", "error_code", "failed_step", "retryable")}
    row.updated_at = datetime.now(timezone.utc) - STALE_AFTER - timedelta(minutes=1)
    env.db.commit()

    assert env.client.post("/api/v1/admin/recover-interrupted", headers=env.h["member"]).status_code == 403
    recovered = env.client.post("/api/v1/admin/recover-interrupted", headers=env.h["admin"])
    assert recovered.json() == {"recovered": 1}
    detail = env.client.get(f"/api/v1/workflows/executions/{eid}", headers=env.h["member"]).json()
    assert detail["status"] == "FAILED" and detail["context"]["error_code"] == "INTERRUPTED"
    assert detail["context"]["failed_step"] == "investigate"

    monkeypatch.setattr(ai_tools, "investigation_graph", Graph(failures=0))
    assert retry(env, eid).json()["status"] == "WAITING_APPROVAL"


def test_recovery_skips_runs_that_are_actually_running(env, monkeypatch):
    monkeypatch.setattr(ai_tools, "investigation_graph", Graph(failures=99))
    eid = UUID(start(env)["execution_id"])
    row = env.db.get(WorkflowExecution, eid)
    row.status = "RUNNING"
    row.updated_at = datetime.now(timezone.utc) - STALE_AFTER - timedelta(minutes=1)
    env.db.commit()
    # A live worker elsewhere holds this run's lock. (The test transaction itself
    # already holds it, so simulate the other holder instead of opening a session.)
    from app.api import workflows
    from app.services import recovery
    held = lambda db, execution_id: execution_id != eid
    monkeypatch.setattr(recovery, "acquire_execution_lock", held)
    monkeypatch.setattr(workflows, "acquire_execution_lock", held)
    assert env.client.post("/api/v1/admin/recover-interrupted", headers=env.h["admin"]).json() == {"recovered": 0}
    assert retry(env, eid).status_code == 409
    assert env.db.get(WorkflowExecution, eid).status == "RUNNING"
