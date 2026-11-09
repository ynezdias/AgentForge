import pytest
from pydantic import ValidationError

from app.schemas.investigation import InvestigationResult


def test_structured_investigation():
    result = InvestigationResult(
        summary="Invoice exceeds purchase order by 15%",
        risk_level="HIGH",
        recommended_action="REQUEST_CORRECTION",
        reasoning="Amount exceeds the 5% tolerance",
    )
    assert result.risk_level == "HIGH"
    assert result.requires_human_approval is True


@pytest.mark.parametrize("override", [
    {"risk_level": "UNKNOWN"},
    {"recommended_action": "PAY_INVOICE"},
    {"requires_human_approval": False},
    {"summary": ""},
    {"reasoning": ""},
])
def test_invalid_or_unreviewed_recommendations_rejected(override):
    values = {
        "summary": "Invoice exceeds purchase order by 15%", "risk_level": "HIGH",
        "recommended_action": "REQUEST_CORRECTION", "reasoning": "Outside tolerance",
        **override,
    }
    with pytest.raises(ValidationError):
        InvestigationResult.model_validate(values)
