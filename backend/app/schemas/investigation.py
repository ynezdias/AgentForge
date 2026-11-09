from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class InvestigationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1)
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    recommended_action: Literal[
        "APPROVE_FOR_REVIEW", "REQUEST_CORRECTION", "ESCALATE_TO_FINANCE"
    ]
    reasoning: str = Field(min_length=1)
    requires_human_approval: Literal[True] = True
