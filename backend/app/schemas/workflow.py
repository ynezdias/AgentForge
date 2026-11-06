from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class WorkflowStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=100)
    type: Literal["tool", "condition", "approval"]
    tool: Literal["invoice.validate", "invoice.resolve"] | None = None
    field: Literal["valid"] | None = None
    operator: Literal["equals"] | None = None
    value: bool | None = None
    on_true: str | None = None
    on_false: str | None = None
    role: Literal["manager"] | None = None

    @model_validator(mode="after")
    def validate_configuration(self):
        if self.type == "tool" and self.tool is None:
            raise ValueError("Tool step requires a tool")
        if self.type == "condition":
            if self.field is None or self.operator is None:
                raise ValueError("Condition requires field and operator")
            if self.value is None:
                raise ValueError("Condition requires value")
            if self.on_true is None or self.on_false is None:
                raise ValueError("Both condition branches are required")
        if self.type == "approval" and self.role is None:
            raise ValueError("Approval step requires a role")
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
        if "__end__" in ids:
            raise ValueError("__end__ is reserved for ending a workflow")
        if sum(step.type == "approval" for step in self.steps) > 1:
            raise ValueError("Only one approval step per execution is supported")
        positions = {step_id: index for index, step_id in enumerate(ids)}
        for index, step in enumerate(self.steps):
            if step.type != "condition":
                continue
            for target in (step.on_true, step.on_false):
                if target == "__end__":
                    continue
                if target not in positions:
                    raise ValueError(f"Unknown branch target: {target}")
                if positions[target] <= index:
                    raise ValueError("Condition branches must point forward")
        return self
