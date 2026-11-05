from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class WorkflowStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=100)
    type: Literal["tool", "condition"]
    tool: Literal["invoice.validate"] | None = None
    field: Literal["valid"] | None = None
    operator: Literal["equals"] | None = None
    value: bool | None = None

    @model_validator(mode="after")
    def validate_configuration(self):
        if self.type == "tool" and self.tool is None:
            raise ValueError("Tool step requires a tool")
        if self.type == "condition":
            if self.field is None or self.operator is None:
                raise ValueError("Condition requires field and operator")
            if self.value is None:
                raise ValueError("Condition requires value")
        return self


class WorkflowDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    steps: list[WorkflowStep] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_ids(self):
        ids = [step.id for step in self.steps]
        if len(ids) != len(set(ids)):
            raise ValueError("Workflow step IDs must be unique")
        return self
