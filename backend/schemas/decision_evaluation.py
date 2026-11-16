"""Read-only observed-association contracts; no predictive accuracy metric."""
from typing import Literal
from pydantic import BaseModel, UUID4, AwareDatetime
from backend.schemas.opportunity_decision import RecommendedAction
from backend.schemas.decision_outcome import OutcomeKind


class EvidenceCounts(BaseModel):
    eligible: int
    evaluated: int
    pending: int
    positive: int
    negative: int
    inconclusive: int


class CategoryEvidence(EvidenceCounts):
    recommendation: RecommendedAction


class DecisionEvaluation(EvidenceCounts):
    policy_version: Literal["latest_observation_v1"] = "latest_observation_v1"
    window: Literal["all_time"] = "all_time"
    coverage: float | None
    evidence_context: Literal["No outcome evidence", "Limited evidence"]
    categories: list[CategoryEvidence]


class EvaluationEvidence(BaseModel):
    decision_id: UUID4
    lead_id: int
    recommendation: RecommendedAction
    decision_recorded_at: AwareDatetime
    outcome_id: UUID4 | None
    kind: OutcomeKind | None
    observed_at: AwareDatetime | None
    outcome_recorded_at: AwareDatetime | None


class EvaluationPage(BaseModel):
    items: list[EvaluationEvidence]
    offset: int
    limit: int
    has_more: bool
