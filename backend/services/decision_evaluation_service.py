"""Deterministic observation arithmetic; no settlement, scoring, or provider calls."""
from backend.repositories.decision_evaluation_repository import DecisionEvaluationRepository
from backend.schemas.decision_evaluation import CategoryEvidence, DecisionEvaluation, EvaluationEvidence, EvaluationPage
from backend.schemas.opportunity_decision import RecommendedAction


class DecisionEvaluationService:
    def __init__(self, db):
        self.db = db
        self.repository = DecisionEvaluationRepository(db)

    def summary(self, org):
        with self.db.no_autoflush:
            stored = {r["recommendation"]: dict(r) for r in self.repository.summary(org)}
        categories = []
        for action in RecommendedAction:
            values = stored.get(action.value, dict(eligible=0, evaluated=0, positive=0, negative=0, inconclusive=0))
            values.pop("recommendation", None)
            categories.append(CategoryEvidence(recommendation=action, pending=values["eligible"] - values["evaluated"], **values))
        totals = {key: sum(getattr(c, key) for c in categories) for key in
                  ("eligible", "evaluated", "pending", "positive", "negative", "inconclusive")}
        return DecisionEvaluation(**totals, categories=categories,
            coverage=totals["evaluated"] / totals["eligible"] if totals["evaluated"] else None,
            evidence_context="Limited evidence" if totals["evaluated"] else "No outcome evidence")

    def page(self, org, limit=20, offset=0):
        if not 1 <= limit <= 100 or not 0 <= offset <= 100000000:
            raise ValueError("Invalid evaluation pagination.")
        with self.db.no_autoflush:
            rows = self.repository.page(org, limit, offset)
        return EvaluationPage(items=[EvaluationEvidence(**r) for r in rows[:limit]],
                              limit=limit, offset=offset, has_more=len(rows) > limit)
