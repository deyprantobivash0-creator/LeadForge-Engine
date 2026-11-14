"""Read composition for current-vs-latest, reusing published P2-A/P2-B reads."""

from backend.decision.decision_change import HISTORY_PREVIEW_LIMIT, compare_decisions
from backend.repositories.decision_ledger_repository import DecisionLedgerRepository
from backend.schemas.decision_change import DecisionChangeResponse
from backend.schemas.decision_ledger import DecisionLedgerHistory
from backend.services.opportunity_decision_service import OpportunityDecisionService


class DecisionComparisonService:
    def __init__(self, db):
        self.db = db

    def get_change(self, lead_id, organization_id):
        with self.db.no_autoflush:
            current = OpportunityDecisionService(self.db).get_decision(lead_id, organization_id)
            if current is None:
                return None
            items, total = DecisionLedgerRepository(self.db).history(
                organization_id, lead_id, HISTORY_PREVIEW_LIMIT, 0)
            latest = items[0] if items else None
            return DecisionChangeResponse(
                current_decision=current, latest_recorded_decision=latest,
                change=compare_decisions(latest, current) if latest is not None else None,
                history=DecisionLedgerHistory(items=items, total=total, limit=HISTORY_PREVIEW_LIMIT, offset=0),
            )
