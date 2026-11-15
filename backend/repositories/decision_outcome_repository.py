"""Scoped outcome storage; business interpretation and settlement belong to services."""
from sqlalchemy import func, select
from backend.database.transactions import in_service_transaction
from backend.models.decision_outcome import DecisionOutcome
from backend.schemas.decision_outcome import OutcomeRecord


class DecisionOutcomeRepository:
    def __init__(self, db):
        self.db = db

    def append(self, values):
        if not in_service_transaction(self.db):
            raise ValueError("Outcome recording requires a service transaction.")
        row = DecisionOutcome(**values)
        self.db.add(row)
        self.db.flush()
        return OutcomeRecord.model_validate(row)

    def history(self, org, lead, decision, limit, offset):
        scope = (DecisionOutcome.organization_id == org, DecisionOutcome.lead_id == lead,
                 DecisionOutcome.decision_id == str(decision))
        total = self.db.scalar(select(func.count()).select_from(DecisionOutcome).where(*scope))
        ordered = select(DecisionOutcome).where(*scope).order_by(
            DecisionOutcome.observed_at.desc(), DecisionOutcome.recorded_at.desc(), DecisionOutcome.id.desc())
        latest = self.db.scalar(ordered.limit(1))
        rows = self.db.scalars(ordered.limit(limit).offset(offset)).all()
        return [OutcomeRecord.model_validate(r) for r in rows], total, latest.kind if latest else None
