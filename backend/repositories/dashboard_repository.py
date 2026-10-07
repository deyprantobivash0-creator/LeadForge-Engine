"""Current Lead snapshot and bounded historical analysis activity."""

from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from backend.models.lead import Lead
from backend.models.lead_analysis import LeadAnalysis
from backend.repositories.lead_analysis_repository import LeadAnalysisRepository


class DashboardRepository:
    @staticmethod
    def _current_join(latest):
        return and_(
            Lead.organization_id == latest.c.organization_id,
            Lead.id == latest.c.lead_id,
            latest.c.rank == 1,
        )

    def snapshot(self, db: Session, organization_id: int) -> dict:
        latest = LeadAnalysisRepository.current_ranked_subquery(organization_id)
        total, analyzed, hot, warm, cold, average = db.execute(
            select(
                func.count(Lead.id),
                func.coalesce(func.sum(case((latest.c.analysis_id.is_not(None), 1), else_=0)), 0),
                func.coalesce(func.sum(case((latest.c.analysis_priority == "Hot", 1), else_=0)), 0),
                func.coalesce(func.sum(case((latest.c.analysis_priority == "Warm", 1), else_=0)), 0),
                func.coalesce(func.sum(case((latest.c.analysis_priority == "Cold", 1), else_=0)), 0),
                func.avg(latest.c.analysis_score),
            )
            .select_from(Lead)
            .outerjoin(latest, self._current_join(latest))
            .where(Lead.organization_id == organization_id)
        ).one()
        lifecycle = {
            status: count for status, count in db.execute(
                select(Lead.status, func.count(Lead.id))
                .where(Lead.organization_id == organization_id)
                .group_by(Lead.status)
            )
        }
        processing = {
            status: count for status, count in db.execute(
                select(Lead.processing_status, func.count(Lead.id))
                .where(Lead.organization_id == organization_id)
                .group_by(Lead.processing_status)
            )
        }
        return {
            "pipeline": {
                "total_leads": total,
                "analyzed_leads": analyzed,
                "unanalyzed_leads": total - analyzed,
                "average_current_score": round(average, 2) if average is not None else None,
            },
            "priority_distribution": {
                "Hot": hot, "Warm": warm, "Cold": cold,
                "Unanalyzed": total - analyzed,
            },
            "lifecycle_distribution": {
                status: lifecycle.get(status, 0)
                for status in ("New", "Qualified", "Contacted", "Meeting", "Won", "Lost")
            },
            "processing_distribution": {
                status: processing.get(status, 0)
                for status in ("pending", "processing", "completed", "failed")
            },
        }

    def top_current(self, db: Session, organization_id: int, limit: int, priority: str | None = None):
        latest = LeadAnalysisRepository.current_ranked_subquery(organization_id)
        query = (
            select(
                Lead.id.label("lead_id"), Lead.company, Lead.status,
                Lead.processing_status, latest.c.analysis_score,
                latest.c.analysis_priority,
            )
            .select_from(Lead)
            .join(latest, self._current_join(latest))
            .where(Lead.organization_id == organization_id)
        )
        if priority is not None:
            query = query.where(latest.c.analysis_priority == priority)
        return db.execute(
            query.order_by(
                latest.c.analysis_score.desc(),
                latest.c.analysis_created_at.desc(),
                latest.c.analysis_id.desc(),
                Lead.id.desc(),
            ).limit(limit)
        ).all()

    def recent_activity(self, db: Session, organization_id: int, limit: int, priority: str | None = None):
        query = (
            select(
                LeadAnalysis.id.label("analysis_id"),
                LeadAnalysis.lead_id, LeadAnalysis.company,
                LeadAnalysis.lead_score, LeadAnalysis.priority,
                LeadAnalysis.created_at,
            )
            .where(LeadAnalysis.organization_id == organization_id)
        )
        if priority is not None:
            query = query.where(LeadAnalysis.priority == priority)
        return db.execute(
            query.order_by(LeadAnalysis.created_at.desc(), LeadAnalysis.id.desc()).limit(limit)
        ).all()
