"""Login, tenant isolation, escalation, and auditable admin overrides (PostgreSQL)."""

import os
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import engine, get_db
from app.main import app
from app.models.audit import AuditEvent
from app.models.business import Invoice, PurchaseOrder, Vendor
from app.models.governance import DecisionOverride
from app.models.workflow import ApprovalRequest, WorkflowExecution
from tests.auth_helpers import TEST_PASSWORD, headers, make_company, make_user

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1", reason="Requires local migrated PostgreSQL"
)

DEFINITION = {
    "name": "Invoice Exception Approval",
    "steps": [
        {"id": "validate", "type": "tool", "tool": "invoice.validate"},
        {"id": "check", "type": "condition", "field": "valid", "operator": "equals",
         "value": False, "on_true": "approval", "on_false": "__end__"},
        {"id": "approval", "type": "approval", "role": "manager"},
        {"id": "resolve", "type": "tool", "tool": "invoice.resolve"},
    ],
}
REASON = "Supplier confirmed the price change in writing."


@pytest.fixture
def env():
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            with Session(bind=connection, join_transaction_mode="create_savepoint") as db:
                app.dependency_overrides[get_db] = lambda: db
                try:
                    acme, globex = make_company(db), make_company(db)
                    users = SimpleNamespace(
                        admin=make_user(db, "admin"), acme=make_user(db, "company", acme),
                        globex=make_user(db, "company", globex))
                    vendor = Vendor(name="Auth test supplier", external_ref=str(uuid4()))
                    db.add(vendor)
                    db.flush()
                    po = PurchaseOrder(vendor_id=vendor.id, total_amount=Decimal("1000"),
                                       company_id=acme.id)
                    db.add(po)
                    db.flush()
                    invoice = Invoice(vendor_id=vendor.id, purchase_order_id=po.id,
                                      amount=Decimal("1150"), company_id=acme.id)
                    db.add(invoice)
                    db.commit()
                    with TestClient(app) as client:
                        yield SimpleNamespace(client=client, db=db, users=users, invoice=invoice,
                                              acme=acme, globex=globex,
                                              h={k: headers(v) for k, v in vars(users).items()})
                finally:
                    app.dependency_overrides.pop(get_db, None)
        finally:
            transaction.rollback()


def run(env, as_user="acme"):
    workflow = env.client.post("/api/v1/workflows", json=DEFINITION, headers=env.h["admin"]).json()
    response = env.client.post(f"/api/v1/workflows/{workflow['id']}/execute",
                               json={"invoice_id": str(env.invoice.id)},
                               headers={**env.h[as_user], "idempotency-key": str(uuid4())})
    assert response.status_code == 200, response.text
    return response.json()


def decide(env, execution_id, decision, as_user="acme"):
    return env.client.post(f"/api/v1/approvals/{execution_id}", json={"decision": decision},
                           headers=env.h[as_user])


def override(env, execution_id, decision, reason=REASON, as_user="admin"):
    return env.client.post(f"/api/v1/admin/executions/{execution_id}/override",
                           json={"decision": decision, "reason": reason}, headers=env.h[as_user])


# --- Login -----------------------------------------------------------------

def login(env, user, portal, password=TEST_PASSWORD):
    return env.client.post("/api/v1/auth/login", json={
        "email": user.email.upper(), "password": password, "portal": portal})


def test_login_issues_token_for_matching_portal(env):
    response = login(env, env.users.acme, "company")
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["role"] == "company"
    assert body["user"]["company_name"] == env.acme.name
    me = env.client.get("/api/v1/auth/me",
                        headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200 and me.json()["email"] == env.users.acme.email
    assert env.users.acme.last_login_at is not None


def test_login_rejections(env):
    assert login(env, env.users.acme, "company", "wrong-password").status_code == 401
    unknown = env.client.post("/api/v1/auth/login", json={
        "email": "nobody@example.test", "password": TEST_PASSWORD, "portal": "admin"})
    assert unknown.status_code == 401
    assert unknown.json() == login(env, env.users.acme, "company", "nope").json()
    assert login(env, env.users.acme, "admin").status_code == 403
    assert login(env, env.users.admin, "company").status_code == 403
    env.users.acme.is_active = False
    env.db.commit()
    assert login(env, env.users.acme, "company").status_code == 401


def test_demo_accounts_refused_in_production(env, monkeypatch):
    env.users.admin.is_demo = True
    env.db.commit()
    assert login(env, env.users.admin, "admin").status_code == 200
    monkeypatch.setenv("APP_ENV", "production")
    assert login(env, env.users.admin, "admin").status_code == 401
    assert env.client.get("/api/v1/auth/me", headers=env.h["admin"]).status_code == 401


def test_token_revocation_and_role_tampering(env):
    assert env.client.get("/api/v1/auth/me", headers=env.h["acme"]).status_code == 200
    env.users.acme.token_version += 1
    env.db.commit()
    assert env.client.get("/api/v1/auth/me", headers=env.h["acme"]).status_code == 401
    # A token whose role claim disagrees with the database is rejected.
    from app.core.security import create_access_token
    token, _ = create_access_token(env.users.globex.id, "admin", env.users.globex.token_version)
    assert env.client.get("/api/v1/admin/overview",
                          headers={"Authorization": f"Bearer {token}"}).status_code == 401


# --- Tenant isolation and role boundaries -----------------------------------

def test_company_users_only_see_their_company(env):
    execution = run(env)
    eid = execution["execution_id"]
    acme_ids = {i["id"] for i in env.client.get("/api/v1/invoices", headers=env.h["acme"]).json()}
    globex_ids = {i["id"] for i in env.client.get("/api/v1/invoices", headers=env.h["globex"]).json()}
    admin_ids = {i["id"] for i in env.client.get("/api/v1/invoices", headers=env.h["admin"]).json()}
    assert str(env.invoice.id) in acme_ids and str(env.invoice.id) in admin_ids
    assert str(env.invoice.id) not in globex_ids
    for path in (f"/api/v1/workflows/executions/{eid}", f"/api/v1/workflows/executions/{eid}/audit",
                 f"/api/v1/invoices/{env.invoice.id}/validate"):
        assert env.client.get(path, headers=env.h["globex"]).status_code == 404
        assert env.client.get(path, headers=env.h["acme"]).status_code == 200
    listed = env.client.get("/api/v1/workflows/executions", headers=env.h["globex"]).json()
    assert eid not in {e["execution_id"] for e in listed}
    assert env.client.get("/api/v1/invoices/purchase-orders", headers=env.h["globex"]).json() == []
    feed = env.client.get("/api/v1/activity", headers=env.h["globex"]).json()
    assert all(event["execution_id"] != eid for event in feed)
    assert any(e["execution_id"] == eid for e in
               env.client.get("/api/v1/activity", headers=env.h["acme"]).json())
    # Another tenant cannot start runs on, decide, or escalate this invoice.
    workflow_id = execution["workflow_id"]
    assert env.client.post(f"/api/v1/workflows/{workflow_id}/execute",
                           json={"invoice_id": str(env.invoice.id)},
                           headers={**env.h["globex"], "idempotency-key": str(uuid4())}).status_code == 404
    assert decide(env, eid, "approve", "globex").status_code == 404
    assert env.client.post(f"/api/v1/approvals/{eid}/escalate", json={"reason": REASON},
                           headers=env.h["globex"]).status_code == 404


def test_admin_only_endpoints(env):
    for path in ("/api/v1/admin/overview", "/api/v1/admin/companies", "/api/v1/admin/overrides"):
        assert env.client.get(path).status_code == 401
        assert env.client.get(path, headers=env.h["acme"]).status_code == 403
        assert env.client.get(path, headers=env.h["admin"]).status_code == 200
    companies = {c["name"]: c for c in env.client.get("/api/v1/admin/companies",
                                                      headers=env.h["admin"]).json()}
    assert companies[env.acme.name]["invoices"] == 1
    assert companies[env.globex.name]["invoices"] == 0


def test_duplicate_invoice_numbers_are_scoped_per_company(env):
    payload = {"supplier_name": "Shared Supplier", "po_amount": "100", "amount": "100",
               "invoice_number": "INV-777", "invoice_date": "2026-11-01"}
    first = env.client.post("/api/v1/invoices", json=payload, headers=env.h["acme"])
    assert first.status_code == 201
    assert env.client.post("/api/v1/invoices", json=payload, headers=env.h["acme"]).status_code == 409
    other = env.client.post("/api/v1/invoices", json=payload, headers=env.h["globex"])
    assert other.status_code == 201
    assert "invoice_id" not in str(other.json().get("detail", ""))
    submitted = env.db.scalars(select(AuditEvent).where(
        AuditEvent.event_type == "INVOICE_SUBMITTED",
        AuditEvent.invoice_id == UUID(first.json()["id"]))).all()
    assert len(submitted) == 1
    assert submitted[0].actor_user_id == env.users.acme.id
    assert submitted[0].company_id == env.acme.id


# --- Escalation ---------------------------------------------------------------

def test_escalated_exception_requires_admin_decision(env):
    eid = run(env)["execution_id"]
    url = f"/api/v1/approvals/{eid}/escalate"
    assert env.client.post(url, json={"reason": "short"}, headers=env.h["acme"]).status_code == 422
    escalated = env.client.post(url, json={"reason": REASON}, headers=env.h["acme"])
    assert escalated.status_code == 200 and escalated.json()["escalated_at"]
    assert env.client.post(url, json={"reason": REASON}, headers=env.h["acme"]).status_code == 409
    assert decide(env, eid, "approve").status_code == 403
    decided = decide(env, eid, "approve", "admin")
    assert decided.status_code == 200 and decided.json()["status"] == "COMPLETED"
    assert decided.json()["approval"]["decided_by"] == env.users.admin.email


# --- Admin overrides ------------------------------------------------------------

def test_override_reject_preserves_original_decision(env):
    eid = run(env)["execution_id"]
    assert decide(env, eid, "approve").json()["status"] == "COMPLETED"
    assert override(env, eid, "reject", as_user="acme").status_code == 403
    assert override(env, eid, "reject", reason="too short").status_code == 422

    response = override(env, eid, "reject")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "REJECTED"
    assert body["approval"]["status"] == "APPROVED"  # Original decision is untouched.
    assert body["approval"]["decided_by"] == env.users.acme.email
    assert body["approval"]["effective_decision"] == "REJECTED"
    [record] = body["overrides"]
    assert record["admin_email"] == env.users.admin.email
    assert (record["original_decision"], record["new_decision"]) == ("APPROVED", "REJECTED")
    assert record["reason"] == REASON and record["created_at"]
    env.db.refresh(env.invoice)
    assert env.invoice.status == "review_rejected"
    approval = env.db.scalar(select(ApprovalRequest).where(ApprovalRequest.execution_id == UUID(eid)))
    assert approval.status == "APPROVED" and approval.decided_by_user_id == env.users.acme.id

    # Same decision again is a no-op conflict, not a second record.
    assert override(env, eid, "reject").status_code == 409
    rows = env.db.scalars(select(DecisionOverride).where(DecisionOverride.execution_id == UUID(eid))).all()
    assert len(rows) == 1
    events = env.db.scalars(select(AuditEvent).where(
        AuditEvent.execution_id == UUID(eid), AuditEvent.event_type == "DECISION_OVERRIDDEN")).all()
    assert len(events) == 1 and events[0].actor_user_id == env.users.admin.id
    assert events[0].payload["original_decided_by"] == env.users.acme.email

    # Overriding back restores the approved outcome and appends a second record.
    restored = override(env, eid, "approve").json()
    assert restored["status"] == "COMPLETED"
    assert [o["new_decision"] for o in restored["overrides"]] == ["REJECTED", "APPROVED"]
    env.db.refresh(env.invoice)
    assert env.invoice.status == "review_approved"


def test_override_approve_runs_resolution_after_rejection(env):
    eid = run(env)["execution_id"]
    rejected = decide(env, eid, "reject").json()
    assert rejected["status"] == "REJECTED"
    assert all(step["step_id"] != "resolve" for step in rejected["steps"])
    approved = override(env, eid, "approve").json()
    assert approved["status"] == "COMPLETED"
    assert any(step["step_id"] == "resolve" and step["status"] == "COMPLETED"
               for step in approved["steps"])
    assert approved["approval"]["status"] == "REJECTED"
    env.db.refresh(env.invoice)
    assert env.invoice.status == "review_approved"


def test_override_requires_a_recorded_decision(env):
    eid = run(env)["execution_id"]
    assert override(env, eid, "approve").status_code == 409  # Still pending.


def test_reopen_creates_linked_run_once(env):
    eid = run(env)["execution_id"]
    decide(env, eid, "reject")
    url = f"/api/v1/admin/executions/{eid}/reopen"
    assert env.client.post(url, json={"reason": REASON}, headers=env.h["acme"]).status_code == 403
    first = env.client.post(url, json={"reason": REASON}, headers=env.h["admin"])
    assert first.status_code == 200
    reopened = first.json()
    assert reopened["execution_id"] != eid
    assert reopened["reopened_from"] == eid
    assert reopened["status"] == "WAITING_APPROVAL"
    assert reopened["company_id"] == str(env.acme.id)
    again = env.client.post(url, json={"reason": REASON}, headers=env.h["admin"]).json()
    assert again["execution_id"] == reopened["execution_id"]
    original = env.db.get(WorkflowExecution, UUID(eid))
    env.db.refresh(original)
    assert original.status == "REJECTED"
    # The company can act on the new run.
    assert decide(env, reopened["execution_id"], "approve").json()["status"] == "COMPLETED"
