"""One scoped SQL statement per response; no ORM row-by-row lookups."""
from sqlalchemy import select, func, and_, case
from backend.models.decision_ledger import DecisionLedger as D
from backend.models.decision_outcome import DecisionOutcome as O


class DecisionEvaluationRepository:
    def __init__(self, db):
        self.db = db

    def evidence(self, org):
        ranked = select(O.id, O.organization_id, O.lead_id, O.decision_id, O.kind,
            O.observed_at, O.recorded_at,
            func.row_number().over(partition_by=(O.organization_id, O.lead_id, O.decision_id),
                order_by=(O.observed_at.desc(), O.recorded_at.desc(), O.id.desc())).label("rank")
        ).where(O.organization_id == org).subquery()
        return select(D.id.label("decision_id"), D.lead_id, D.recommended_action.label("recommendation"),
            D.recorded_at.label("decision_recorded_at"), ranked.c.id.label("outcome_id"), ranked.c.kind,
            ranked.c.observed_at, ranked.c.recorded_at.label("outcome_recorded_at")).outerjoin(ranked, and_(
                ranked.c.organization_id == D.organization_id, ranked.c.lead_id == D.lead_id,
                ranked.c.decision_id == D.id, ranked.c.rank == 1)).where(D.organization_id == org)

    def summary(self, org):
        rows = self.evidence(org).subquery()
        return self.db.execute(select(rows.c.recommendation, func.count().label("eligible"),
            func.sum(case((rows.c.outcome_id.is_not(None), 1), else_=0)).label("evaluated"),
            func.sum(case((rows.c.kind.in_(["Qualified", "Meeting", "Won"]), 1), else_=0)).label("positive"),
            func.sum(case((rows.c.kind == "Lost", 1), else_=0)).label("negative"),
            func.sum(case((rows.c.kind == "Contacted", 1), else_=0)).label("inconclusive")
        ).group_by(rows.c.recommendation)).mappings().all()

    def page(self, org, limit, offset):
        rows = self.evidence(org).subquery()
        return self.db.execute(select(rows).order_by(rows.c.decision_recorded_at.desc(), rows.c.decision_id.desc())
            .offset(offset).limit(limit + 1)).mappings().all()
