"""Tenant/lead-scoped append and bounded history, with no scoring or settlement."""

from sqlalchemy import func, select

from backend.database.transactions import in_service_transaction
from backend.models.decision_ledger import DecisionLedger
from backend.repositories.lead_repository import LeadRepository
from backend.schemas.decision_ledger import DecisionLedgerRecord


class DecisionLedgerRepository:
    def __init__(self, db):
        self.db = db

    def possible_lead_id(self, lead_id):
        # Shared HTTP paths allow int64; PostgreSQL's physical Lead key is int4.
        return not (self.db.get_bind().dialect.name == "postgresql" and lead_id > 2**31 - 1)

    def lead_exists(self, lead_id, organization_id):
        return (self.possible_lead_id(lead_id) and
                LeadRepository(self.db).get_lead_by_id(lead_id, organization_id) is not None)

    def append(self, snapshot: DecisionLedgerRecord) -> DecisionLedgerRecord:
        if not in_service_transaction(self.db):
            raise ValueError("Decision recording requires a caller-owned service transaction.")
        if type(snapshot) is not DecisionLedgerRecord:
            raise ValueError("A typed Decision Ledger snapshot is required.")
        s = DecisionLedgerRecord.model_validate(snapshot)
        values = dict(id=str(s.id), organization_id=s.organization_id, lead_id=s.lead_id,
            decision_version=s.decision_version, opportunity_score=s.opportunity_score,
            fit_score=s.fit_score, readiness_score=s.readiness_score, confidence=s.confidence,
            recommended_action=s.recommended_action.value, human_review_required=s.human_review_required,
            reasons=list(s.reasons), evidence=[dict(signal=e.signal, observed_value=e.observed_value,
                effect=e.effect, source=e.source) for e in s.evidence],
            risk_flags=[r.value for r in s.risk_flags], missing_signals=[m.value for m in s.missing_signals],
            decision_generated_at=s.decision_generated_at, recorded_at=s.recorded_at)
        # Validate nested primitive copies too: even an internally constructed
        # model instance must not bypass JSON cardinality/text bounds.
        DecisionLedgerRecord.model_validate(values)
        row = DecisionLedger(**values)
        self.db.add(row)
        self.db.flush()
        return DecisionLedgerRecord.from_row(row)

    def history(self, organization_id, lead_id, limit, offset):
        if not 1 <= limit <= 100 or not 0 <= offset <= 100000000:
            raise ValueError("Invalid decision history pagination.")
        scope = (DecisionLedger.organization_id == organization_id, DecisionLedger.lead_id == lead_id)
        total = self.db.scalar(select(func.count()).select_from(DecisionLedger).where(*scope))
        rows = self.db.scalars(select(DecisionLedger).where(*scope).order_by(
            DecisionLedger.recorded_at.desc(), DecisionLedger.id.desc()).limit(limit).offset(offset)).all()
        return [DecisionLedgerRecord.from_row(row) for row in rows], total

    def get(self, organization_id, lead_id, decision_id):
        row = self.db.scalar(select(DecisionLedger).where(
            DecisionLedger.organization_id == organization_id, DecisionLedger.lead_id == lead_id,
            DecisionLedger.id == str(decision_id)).limit(1))
        return DecisionLedgerRecord.from_row(row) if row is not None else None
