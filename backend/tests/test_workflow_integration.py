"""Opt in with RUN_DB_TESTS=1; all data is rolled back after each test."""

import os
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.session import engine, get_db
from app.main import app
from app.models.business import Invoice, PurchaseOrder, Vendor


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1", reason="Requires local migrated PostgreSQL"
)


def test_workflow_execution_and_idempotency():
    with engine.connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection, join_transaction_mode="create_savepoint") as db:
            def override_db():
                yield db

            app.dependency_overrides[get_db] = override_db
            try:
                vendor = Vendor(name="Workflow test", external_ref=str(uuid4()))
                db.add(vendor)
                db.flush()
                po = PurchaseOrder(vendor_id=vendor.id, total_amount=Decimal("1000"))
                db.add(po)
                db.flush()
                invoice = Invoice(vendor_id=vendor.id, purchase_order_id=po.id,
                                  amount=Decimal("1150"))
                db.add(invoice)
                db.commit()
                with TestClient(app) as client:
                    created = client.post("/api/v1/workflows", json={
                        "name": "Invoice Validation Workflow",
                        "steps": [
                            {"id": "validate_invoice", "type": "tool",
                             "tool": "invoice.validate"},
                            {"id": "check_validity", "type": "condition",
                             "field": "valid", "operator": "equals", "value": False},
                        ],
                    })
                    assert created.status_code == 201
                    url = f'/api/v1/workflows/{created.json()["id"]}/execute'
                    headers = {"idempotency-key": str(uuid4())}
                    payload = {"invoice_id": str(invoice.id)}
                    response = client.post(url, headers=headers, json=payload)
                    assert response.status_code == 200
                    execution = response.json()
                    assert execution["status"] == "COMPLETED"
                    assert execution["context"] == {
                        "valid": False, "issues": ["AMOUNT_DISCREPANCY"],
                        "discrepancy_percentage": "15.00", "condition_matched": True,
                    }
                    assert [step["step_id"] for step in execution["steps"]] == [
                        "validate_invoice", "check_validity"
                    ]
                    replay = client.post(url, headers=headers, json=payload)
                    assert replay.json() == execution
                    conflict = client.post(url, headers=headers,
                                           json={"invoice_id": str(uuid4())})
                    assert conflict.status_code == 409
                    detail = client.get(
                        f'/api/v1/workflows/executions/{execution["execution_id"]}'
                    )
                    assert detail.json() == execution
            finally:
                app.dependency_overrides.pop(get_db, None)
                transaction.rollback()
