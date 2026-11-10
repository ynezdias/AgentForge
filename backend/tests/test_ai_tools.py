from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services import ai_tools


def invoice_pair(amount="1150.00"):
    vendor_id = uuid4()
    return (
        SimpleNamespace(id=uuid4(), vendor_id=vendor_id,
                        amount=Decimal(amount), currency="USD"),
        SimpleNamespace(vendor_id=vendor_id, total_amount=Decimal("1000.00"),
                        currency="USD"),
    )


def test_ai_investigation(monkeypatch):
    invoice, po = invoice_pair()

    class FakeGraph:
        def invoke(self, state):
            assert state["invoice_facts"]["validation"]["discrepancy_percentage"] == 15.0
            return {"investigation": {
                "summary": "15% overbilling", "risk_level": "HIGH",
                "recommended_action": "REQUEST_CORRECTION",
                "reasoning": "Exceeds tolerance", "requires_human_approval": True,
            }}

    monkeypatch.setattr(ai_tools, "investigation_graph", FakeGraph())
    result = ai_tools.investigate_invoice_tool(invoice, po)
    assert result["skipped"] is False
    assert result["recommendation"]["risk_level"] == "HIGH"
    assert result["recommendation"]["requires_human_approval"] is True
    assert result["facts"]["invoice_amount"] == "1150.00"


def test_valid_invoice_skips_ai(monkeypatch):
    class NoCalls:
        def invoke(self, state):
            pytest.fail("Valid invoice must not invoke AI")

    monkeypatch.setattr(ai_tools, "investigation_graph", NoCalls())
    assert ai_tools.investigate_invoice_tool(*invoice_pair("1000.00")) == {
        "skipped": True, "reason": "No invoice exception detected",
    }


def test_provider_error_is_sanitized(monkeypatch):
    class FailedGraph:
        def invoke(self, state):
            raise RuntimeError("private-provider-secret")

    monkeypatch.setattr(ai_tools, "investigation_graph", FailedGraph())
    with pytest.raises(RuntimeError, match="^AI investigation failed$"):
        ai_tools.investigate_invoice_tool(*invoice_pair())
