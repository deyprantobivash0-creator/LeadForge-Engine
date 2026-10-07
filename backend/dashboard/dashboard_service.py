from sqlalchemy.orm import Session

from backend.repositories.dashboard_repository import DashboardRepository
from backend.repositories.lead_analysis_repository import LeadAnalysisRepository


class DashboardService:

    def __init__(self, db: Session):
        self.db = db
        self.repository = DashboardRepository()
        self.activity_repository = LeadAnalysisRepository()

    def current_overview(self, organization_id: int, limit: int = 5, priority: str | None = None) -> dict:
        snapshot = self.repository.snapshot(self.db, organization_id)
        top_opportunities = self.repository.top_current(self.db, organization_id, limit, priority)
        recent_activity = self.repository.recent_activity(self.db, organization_id, limit, priority)

        return {
            **snapshot,
            "top_opportunities": [
                {
                    "lead_id": row.lead_id,
                    "company": row.company,
                    "status": row.status,
                    "processing_status": row.processing_status,
                    "priority": row.analysis_priority,
                    "lead_score": row.analysis_score,
                }
                for row in top_opportunities
            ],
            "recent_analysis_activity": [
                {
                    "analysis_id": row.analysis_id,
                    "lead_id": row.lead_id,
                    "company": row.company,
                    "priority": row.priority,
                    "lead_score": row.lead_score,
                    "created_at": row.created_at,
                }
                for row in recent_activity
            ],
        }

    def legacy_overview(self, organization_id: int, limit: int = 5, priority: str | None = None) -> dict:
        """Preserve the original history-row contract for existing callers."""
        summary = self.activity_repository.summary(self.db, organization_id)
        top = self.activity_repository.top_by_score(self.db, organization_id, limit, priority=priority)
        recent = self.activity_repository.recent(self.db, organization_id, limit, priority=priority)
        return {
            **summary,
            "top_opportunities": [
                {"id": row.id, "company": row.company, "email": row.email,
                 "priority": row.priority, "lead_score": row.lead_score}
                for row in top
            ],
            "recent_analyses": [
                {"id": row.id, "company": row.company, "email": row.email,
                 "priority": row.priority, "lead_score": row.lead_score,
                 "created_at": row.created_at}
                for row in recent
            ],
        }

    def overview(self, organization_id: int, limit: int = 5, priority: str | None = None) -> dict:
        """Retain the original service entry point for history-based callers."""
        return self.legacy_overview(organization_id, limit, priority)
