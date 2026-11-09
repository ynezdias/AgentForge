import json
from unittest.mock import MagicMock

from app.schemas.investigation import InvestigationResult
from app.services import investigation_agent


def test_graph_uses_structured_output_and_only_supplied_facts(monkeypatch):
    constructor = MagicMock()
    constructor.return_value.with_structured_output.return_value.invoke.return_value = (
        InvestigationResult(
            summary="Invoice exceeds purchase order by 15%", risk_level="HIGH",
            recommended_action="REQUEST_CORRECTION", reasoning="Outside 5% tolerance",
        )
    )
    monkeypatch.setattr(investigation_agent, "ChatGoogleGenerativeAI", constructor)
    facts = {"invoice_amount": "1150.00", "purchase_order_amount": "1000.00",
             "validation": {"discrepancy_percentage": 15.0}}
    state = investigation_agent.investigation_graph.invoke({"invoice_facts": facts})
    assert state["investigation"]["requires_human_approval"] is True
    constructor.return_value.with_structured_output.assert_called_once_with(
        InvestigationResult, method="json_schema"
    )
    messages = constructor.return_value.with_structured_output.return_value.invoke.call_args.args[0]
    assert json.loads(messages[1][1]) == facts
    assert "never authorize payments or modify invoices" in messages[0][1]
