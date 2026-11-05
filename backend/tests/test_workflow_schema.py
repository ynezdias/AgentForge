import pytest
from pydantic import ValidationError

from app.schemas.workflow import WorkflowDefinition


def test_false_condition_value_is_allowed():
    definition = WorkflowDefinition.model_validate({
        "name": "Invoice validation",
        "steps": [
            {"id": "validate", "type": "tool", "tool": "invoice.validate"},
            {"id": "check", "type": "condition", "field": "valid",
             "operator": "equals", "value": False},
        ],
    })
    assert definition.steps[1].value is False


@pytest.mark.parametrize("steps", [
    [],
    [{"id": "a", "type": "tool"}],
    [{"id": "a", "type": "tool", "tool": "python.execute"}],
    [{"id": "a", "type": "condition", "field": "valid", "operator": "equals"}],
    [{"id": "a", "type": "condition", "value": False}],
    [{"id": "a", "type": "tool", "tool": "invoice.validate"}] * 2,
    [{"id": "a", "type": "tool", "tool": "invoice.validate", "code": "print(1)"}],
])
def test_unsupported_or_invalid_workflows_are_rejected(steps):
    with pytest.raises(ValidationError):
        WorkflowDefinition.model_validate({"name": "Invalid", "steps": steps})
