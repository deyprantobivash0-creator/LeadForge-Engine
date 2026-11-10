"""Historical contract stores its own version; it never reads the live policy."""

from datetime import datetime
from uuid import uuid4

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, UUID4

from backend.schemas.opportunity_decision import (
    DecisionEvidence, DecisionRisk, Explanation, MissingSignal,
    OpportunityDecision, RecommendedAction, Score,
)


class RecordDecisionRequest(BaseModel):
    """Optional empty body. Clients cannot submit snapshot or tenant fields."""

    model_config = ConfigDict(extra="forbid")


class DecisionLedgerRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, revalidate_instances="always")

    id: UUID4
    organization_id: int = Field(strict=True, ge=1)
    lead_id: int = Field(strict=True, ge=1)
    decision_version: str = Field(min_length=1, max_length=64)
    opportunity_score: Score
    fit_score: Score
    readiness_score: Score
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    recommended_action: RecommendedAction
    human_review_required: bool = Field(strict=True)
    reasons: list[Explanation] = Field(min_length=1, max_length=12)
    evidence: list[DecisionEvidence] = Field(max_length=12)
    risk_flags: list[DecisionRisk] = Field(max_length=8)
    missing_signals: list[MissingSignal] = Field(max_length=6)
    decision_generated_at: AwareDatetime
    recorded_at: AwareDatetime

    @classmethod
    def capture(cls, decision: OpportunityDecision, recorded_at: datetime):
        # Explicit allowlist, with fresh containers. No ORM, auth, request or
        # arbitrary provider metadata can enter this snapshot mapping.
        return cls(id=uuid4(), organization_id=decision.organization_id, lead_id=decision.lead_id,
            decision_version=decision.decision_version, opportunity_score=decision.opportunity_score,
            fit_score=decision.fit_score, readiness_score=decision.readiness_score,
            confidence=decision.confidence, recommended_action=decision.recommended_action,
            human_review_required=decision.human_review_required, reasons=list(decision.reasons),
            evidence=[DecisionEvidence(signal=e.signal, observed_value=e.observed_value,
                                      effect=e.effect, source=e.source) for e in decision.evidence],
            risk_flags=list(decision.risk_flags), missing_signals=list(decision.missing_signals),
            decision_generated_at=decision.generated_at, recorded_at=recorded_at)

    @classmethod
    def from_row(cls, row):
        # Read stored snapshot only, never Lead/current-policy-derived fields.
        return cls(id=row.id, organization_id=row.organization_id, lead_id=row.lead_id,
            decision_version=row.decision_version, opportunity_score=row.opportunity_score,
            fit_score=row.fit_score, readiness_score=row.readiness_score, confidence=row.confidence,
            recommended_action=row.recommended_action, human_review_required=row.human_review_required,
            reasons=row.reasons, evidence=row.evidence,
            risk_flags=row.risk_flags, missing_signals=row.missing_signals,
            decision_generated_at=row.decision_generated_at, recorded_at=row.recorded_at)


class DecisionLedgerHistory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[DecisionLedgerRecord] = Field(max_length=100)
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0, le=100000000)
