"""Tenant-scoped read composition; settlement remains with the existing caller."""

from sqlalchemy.orm import Session

from backend.decision.opportunity_policy import evaluate, extract_features
from backend.repositories.lead_repository import LeadRepository
from backend.repositories.lead_analysis_repository import LeadAnalysisRepository
from backend.schemas.opportunity_decision import OpportunityDecision


class OpportunityDecisionService:
    def __init__(self, db: Session):
        self.db = db

    def get_decision(self, lead_id: int, organization_id: int) -> OpportunityDecision | None:
        # The route supplies an authenticated active-membership organization.
        # Match existing read services; do not commit an authorization autobegin
        # or flush any pending caller work merely to compute a recommendation.
        if type(organization_id) is not int or organization_id <= 0:
            raise ValueError("An authorized organization is required")
        # The shared HTTP contract permits int64, while the current PostgreSQL
        # schema uses int4. psycopg's Integer bind casts overflow before a SELECT
        # can return no rows. Such an ID cannot exist in this physical schema.
        if self.db.get_bind().dialect.name == "postgresql" and lead_id > 2**31 - 1:
            return None
        with self.db.no_autoflush:
            lead = LeadRepository(self.db).get_lead_by_id(lead_id, organization_id)
            if lead is None:
                return None
            analysis = LeadAnalysisRepository().get_current_for_lead(self.db, lead_id, organization_id)
            return evaluate(extract_features(lead, analysis))
