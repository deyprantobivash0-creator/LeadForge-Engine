"""Append-only product history, separate from the security audit stream."""

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, Float, ForeignKey, ForeignKeyConstraint, Index, Integer, JSON, String, event
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base
from backend.models.audit_event import AuditUTCDateTime


class DecisionLedger(Base):
    __tablename__ = "decision_ledger"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False)
    lead_id: Mapped[int] = mapped_column(Integer, nullable=False)
    decision_version: Mapped[str] = mapped_column(String(64), nullable=False)
    opportunity_score: Mapped[int] = mapped_column(Integer, nullable=False)
    fit_score: Mapped[int] = mapped_column(Integer, nullable=False)
    readiness_score: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    recommended_action: Mapped[str] = mapped_column(String(32), nullable=False)
    human_review_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reasons: Mapped[list] = mapped_column(JSON(none_as_null=True), nullable=False)
    evidence: Mapped[list] = mapped_column(JSON(none_as_null=True), nullable=False)
    risk_flags: Mapped[list] = mapped_column(JSON(none_as_null=True), nullable=False)
    missing_signals: Mapped[list] = mapped_column(JSON(none_as_null=True), nullable=False)
    decision_generated_at: Mapped[datetime] = mapped_column(AuditUTCDateTime(), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(AuditUTCDateTime(), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(["organization_id", "lead_id"], ["leads.organization_id", "leads.id"],
                             name="fk_decision_ledger_organization_lead", ondelete="RESTRICT"),
        CheckConstraint("organization_id > 0 AND lead_id > 0", name="positive_ownership"),
        CheckConstraint("length(id) = 36 AND length(decision_version) BETWEEN 1 AND 64", name="identity_bounds"),
        CheckConstraint("opportunity_score BETWEEN 0 AND 100 AND fit_score BETWEEN 0 AND 100 "
                        "AND readiness_score BETWEEN 0 AND 100 AND confidence >= 0 AND confidence <= 1", name="score_bounds"),
        CheckConstraint("recommended_action IN ('RESEARCH_MORE','HUMAN_REVIEW','QUALIFY','PREPARE_OUTREACH','NURTURE','DEPRIORITIZE') "
                        "AND human_review_required IN (TRUE,FALSE)", name="decision_domains"),
        CheckConstraint("length(CAST(reasons AS TEXT)) <= 65536 AND length(CAST(evidence AS TEXT)) <= 131072 "
                        "AND length(CAST(risk_flags AS TEXT)) <= 1024 AND length(CAST(missing_signals AS TEXT)) <= 1024", name="json_bounds"),
        Index("ix_decision_ledger_org_lead_time", "organization_id", "lead_id", "recorded_at", "id"),
    )


@event.listens_for(DecisionLedger, "before_update")
@event.listens_for(DecisionLedger, "before_delete")
def _reject_historical_mutation(_mapper, _connection, _target):
    # Alembic additionally installs database UPDATE/DELETE rejection triggers.
    raise ValueError("Decision Ledger records are immutable.")
