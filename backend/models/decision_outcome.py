"""Append-only observations linked to immutable Decision Ledger identities."""
from datetime import datetime
from sqlalchemy import CheckConstraint, ForeignKey, ForeignKeyConstraint, Index, Integer, String, event
from sqlalchemy.orm import Mapped, mapped_column
from backend.database.base import Base
from backend.models.audit_event import AuditUTCDateTime


class DecisionOutcome(Base):
    __tablename__ = "decision_outcomes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[int] = mapped_column(Integer, nullable=False)
    lead_id: Mapped[int] = mapped_column(Integer, nullable=False)
    decision_id: Mapped[str] = mapped_column(String(36), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(AuditUTCDateTime(), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(AuditUTCDateTime(), nullable=False)
    recorded_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    __table_args__ = (
        ForeignKeyConstraint(["organization_id", "lead_id", "decision_id"],
            ["decision_ledger.organization_id", "decision_ledger.lead_id", "decision_ledger.id"],
            ondelete="RESTRICT", name="fk_outcome_scoped_decision"),
        CheckConstraint("kind IN ('Contacted','Qualified','Meeting','Won','Lost')", name="outcome_kind"),
        CheckConstraint("organization_id > 0 AND lead_id > 0 AND recorded_by_user_id > 0 AND length(id) = 36", name="outcome_identity"),
        CheckConstraint("note IS NULL OR length(note) <= 1000", name="outcome_note"),
        CheckConstraint("observed_at <= recorded_at", name="outcome_time"),
        Index("ix_outcomes_decision_time", "organization_id", "lead_id", "decision_id", "observed_at", "recorded_at", "id"),
    )


@event.listens_for(DecisionOutcome, "before_update")
@event.listens_for(DecisionOutcome, "before_delete")
def reject_outcome_mutation(_mapper, _connection, _target):
    raise ValueError("Outcome evidence is immutable.")
