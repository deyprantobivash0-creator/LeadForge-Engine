"""Validated, limited provider assessments and authoritative persisted result."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal["lead_data", "derived"]
    field: Literal["company", "email", "source", "industry"]
    value: str = Field(min_length=1, max_length=200)
    reasoning: str = Field(min_length=1, max_length=300)


class StageAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: int = Field(strict=True, ge=0, le=100)
    summary: str = Field(min_length=1, max_length=300)
    evidence: list[Evidence] = Field(default_factory=list, max_length=8)


class FinalDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lead_score: int = Field(strict=True, ge=0, le=100)
    priority: Literal["Hot", "Warm", "Cold"]
    recommended_action: str = Field(min_length=1, max_length=200)


class LeadBrainResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    company: StageAssessment
    contact: StageAssessment
    intent: StageAssessment
    final_decision: FinalDecision
