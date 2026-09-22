from sqlalchemy.orm import Session

from backend.repositories.lead_analysis_repository import (
    LeadAnalysisRepository,
)


class DashboardService:

    def __init__(self, db: Session):
        self.db = db
        self.repository = LeadAnalysisRepository()

    def overview(self) -> dict:

        analyses = self.repository.get_all(self.db)

        total_leads = len(analyses)

        hot_leads = sum(
            1 for lead in analyses
            if lead.priority == "Hot"
        )

        warm_leads = sum(
            1 for lead in analyses
            if lead.priority == "Warm"
        )

        cold_leads = sum(
            1 for lead in analyses
            if lead.priority == "Cold"
        )

        average_score = round(
            sum(lead.lead_score for lead in analyses)
            / total_leads,
            2,
        ) if total_leads else 0

        top_opportunities = sorted(
            analyses,
            key=lambda lead: lead.lead_score,
            reverse=True,
        )[:5]

        recent_analyses = analyses[:5]

        return {
            "total_leads": total_leads,
            "hot_leads": hot_leads,
            "warm_leads": warm_leads,
            "cold_leads": cold_leads,
            "average_lead_score": average_score,
            "top_opportunities": [
                {
                    "id": lead.id,
                    "company": lead.company,
                    "email": lead.email,
                    "priority": lead.priority,
                    "lead_score": lead.lead_score,
                }
                for lead in top_opportunities
            ],
            "recent_analyses": [
                {
                    "id": lead.id,
                    "company": lead.company,
                    "email": lead.email,
                    "priority": lead.priority,
                    "lead_score": lead.lead_score,
                    "created_at": lead.created_at,
                }
                for lead in recent_analyses
            ],
        }