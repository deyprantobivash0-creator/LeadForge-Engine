"""Bounded, read-only Revenue Brain v1 response; no ORM or provider payloads."""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class RecommendedAction(StrEnum):
    RESEARCH_MORE = "RESEARCH_MORE"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    QUALIFY = "QUALIFY"
    PREPARE_OUTREACH = "PREPARE_OUTREACH"
    NURTURE = "NURTURE"
    DEPRIORITIZE = "DEPRIORITIZE"


class DecisionRisk(StrEnum):
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    CONFLICTING_SIGNALS = "CONFLICTING_SIGNALS"
    INVALID_ANALYSIS = "INVALID_ANALYSIS"
    STALE_ANALYSIS = "STALE_ANALYSIS"
    UNKNOWN_LIFECYCLE = "UNKNOWN_LIFECYCLE"
    LOW_ASSESSED_FIT = "LOW_ASSESSED_FIT"
    ANALYSIS_IN_PROGRESS = "ANALYSIS_IN_PROGRESS"


class MissingSignal(StrEnum):
    COMPANY_PROFILE = "company_profile"
    CONTACT_DETAILS = "contact_details"
    COMPANY_ASSESSMENT = "company_assessment"
    CONTACT_ASSESSMENT = "contact_assessment"
    INTENT_ASSESSMENT = "intent_assessment"
    LIFECYCLE_STATE = "lifecycle_state"


Score = Annotated[int, Field(strict=True, ge=0, le=100)]
Explanation = Annotated[str, Field(min_length=1, max_length=240)]


class DecisionEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    signal: str = Field(min_length=1, max_length=64)
    observed_value: str = Field(min_length=1, max_length=160)
    effect: Explanation
    source: Literal["lead_record", "stored_assessment", "policy"]


class OpportunityDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    lead_id: int = Field(strict=True, ge=1)
    organization_id: int = Field(strict=True, ge=1)
    decision_version: Literal["revenue_brain_v1"] = "revenue_brain_v1"
    opportunity_score: Score
    fit_score: Score
    readiness_score: Score
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    recommended_action: RecommendedAction
    human_review_required: bool
    reasons: list[Explanation] = Field(min_length=1, max_length=12)
    evidence: list[DecisionEvidence] = Field(max_length=12)
    risk_flags: list[DecisionRisk] = Field(max_length=8)
    missing_signals: list[MissingSignal] = Field(max_length=6)
    generated_at: AwareDatetime
