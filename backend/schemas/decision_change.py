"""Derived comparison contracts. Current computation has no ledger identity."""

from enum import StrEnum
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, UUID4

from backend.schemas.decision_ledger import DecisionLedgerHistory, DecisionLedgerRecord
from backend.schemas.opportunity_decision import (
    DecisionEvidence, DecisionRisk, Explanation, MissingSignal,
    OpportunityDecision, RecommendedAction,
)


class ChangeDirection(StrEnum):
    IMPROVED = "IMPROVED"
    DECLINED = "DECLINED"
    MIXED = "MIXED"
    UNCHANGED = "UNCHANGED"


class MaterialFactor(StrEnum):
    OPPORTUNITY = "opportunity_threshold"
    FIT = "fit_threshold"
    READINESS = "readiness_threshold"
    CONFIDENCE = "confidence_threshold"
    RECOMMENDATION = "recommendation"
    HUMAN_REVIEW = "human_review"
    RISKS = "risks"
    MISSING_SIGNALS = "missing_signals"
    PROVENANCE = "evidence_provenance"
    POLICY = "policy_version"


class DecisionChange(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    comparison_version: Literal["decision_change_v1"] = "decision_change_v1"
    from_decision_id: UUID4
    from_recorded_at: AwareDatetime
    to_kind: Literal["current_computed"] = "current_computed"
    to_generated_at: AwareDatetime
    previous_policy_version: str = Field(min_length=1, max_length=64)
    current_policy_version: str = Field(min_length=1, max_length=64)
    policy_version_changed: bool
    opportunity_score_delta: int = Field(strict=True, ge=-100, le=100)
    fit_score_delta: int = Field(strict=True, ge=-100, le=100)
    readiness_score_delta: int = Field(strict=True, ge=-100, le=100)
    confidence_delta: float = Field(ge=-1, le=1, allow_inf_nan=False)
    recommendation_changed: bool
    previous_recommendation: RecommendedAction
    current_recommendation: RecommendedAction
    human_review_changed: bool
    previous_human_review_required: bool
    current_human_review_required: bool
    added_risk_flags: list[DecisionRisk] = Field(max_length=8)
    removed_risk_flags: list[DecisionRisk] = Field(max_length=8)
    added_missing_signals: list[MissingSignal] = Field(max_length=6)
    resolved_missing_signals: list[MissingSignal] = Field(max_length=6)
    evidence_changed: bool
    evidence_provenance_changed: bool
    added_evidence: list[DecisionEvidence] = Field(max_length=12)
    removed_evidence: list[DecisionEvidence] = Field(max_length=12)
    reasons_changed: bool
    added_reasons: list[Explanation] = Field(max_length=12)
    removed_reasons: list[Explanation] = Field(max_length=12)
    overall_direction: ChangeDirection
    material_change: bool
    material_factors: list[MaterialFactor] = Field(max_length=10)
    explanations: list[Explanation] = Field(min_length=1, max_length=16)


class DecisionChangeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_decision: OpportunityDecision
    latest_recorded_decision: DecisionLedgerRecord | None
    change: DecisionChange | None
    history: DecisionLedgerHistory
