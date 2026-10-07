from sqlalchemy.orm import Session

from backend.repositories.lead_repository import LeadRepository
from backend.repositories.lead_analysis_repository import (
    LeadAnalysisRepository,
)


class LeadIntelligenceService:

    def __init__(self, db: Session):
        self.db = db
        self.lead_repository = LeadRepository(db)
        self.analysis_repository = LeadAnalysisRepository()

    def get_by_id(
        self,
        lead_id: int,
        organization_id: int,
    ):

        lead = self.lead_repository.get_lead_by_id(
            lead_id=lead_id,
            organization_id=organization_id,
        )

        if not lead:
            return None

        analysis = self.analysis_repository.get_current_for_lead(
            self.db,
            lead.id,
            organization_id=organization_id,
        )

        return {
            "id": lead.id,
            "company": lead.company,
            "email": lead.email,
            "source": lead.source,
            "analysis": (
                {
                    "id": analysis.id,
                    "lead_id": analysis.lead_id,
                    "priority": analysis.priority,
                    "lead_score": analysis.lead_score,
                    "result": analysis.result,
                    "created_at": analysis.created_at,
                }
                if analysis
                else None
            ),
        }

    def get_by_email(
        self,
        email: str,
        organization_id: int,
    ):

        lead = self.lead_repository.get_lead_by_email(
            email=email,
            organization_id=organization_id,
        )

        if not lead:
            return None

        return self.get_by_id(
            lead.id,
            organization_id,
        )
