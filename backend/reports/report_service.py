from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from backend.repositories.lead_analysis_repository import (
    LeadAnalysisRepository,
)


class ReportService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = LeadAnalysisRepository()

    @staticmethod
    def _now() -> datetime:
        # LeadAnalysis stores naïve UTC timestamps; convert at this boundary.
        return datetime.now(timezone.utc).replace(tzinfo=None)

    def generate_report(
        self,
        organization_id: int,
        start_date: datetime,
        end_date: datetime,
        period: str,
        limit: int = 5,
        priority: str | None = None,
    ) -> dict:
        summary = self.repository.summary(
            self.db, organization_id, start_date, end_date,
        )
        top_leads = self.repository.top_by_score(
            self.db, organization_id, limit,
            priority=priority, start_date=start_date, end_date=end_date,
        )

        top_leads_data = [
            {
                "id": lead.id,
                "company": lead.company,
                "email": lead.email,
                "priority": lead.priority,
                "lead_score": lead.lead_score,
            }
            for lead in top_leads
        ]

        return {
            "period": period,
            "start_date": start_date,
            "end_date": end_date,
            **summary,
            "top_leads": top_leads_data,
        }

    def daily_report(self, organization_id: int, limit: int = 5, priority: str | None = None) -> dict:
        now = self._now()

        start_date = datetime(
            now.year,
            now.month,
            now.day,
        )

        end_date = start_date + timedelta(days=1)

        return self.generate_report(
            organization_id=organization_id,
            start_date=start_date,
            end_date=end_date,
            period="daily",
            limit=limit,
            priority=priority,
        )

    def weekly_report(self, organization_id: int, limit: int = 5, priority: str | None = None) -> dict:
        now = self._now()

        start_date = now - timedelta(days=7)

        return self.generate_report(
            organization_id=organization_id,
            start_date=start_date,
            end_date=now,
            period="weekly",
            limit=limit,
            priority=priority,
        )

    def monthly_report(self, organization_id: int, limit: int = 5, priority: str | None = None) -> dict:
        now = self._now()

        start_date = now - timedelta(days=30)

        return self.generate_report(
            organization_id=organization_id,
            start_date=start_date,
            end_date=now,
            period="monthly",
            limit=limit,
            priority=priority,
        )

    def executive_report(self, organization_id: int) -> dict:
        report = self.monthly_report(organization_id)
        recommendations = []

        if report["hot_leads"] > 0:
            recommendations.append(
                "Prioritize Hot leads for immediate follow-up."
            )

        if report["average_lead_score"] >= 70:
            recommendations.append(
                "Overall lead quality is strong. "
                "Focus resources on high-scoring accounts."
            )

        elif report["average_lead_score"] >= 40:
            recommendations.append(
                "Lead quality is moderate. "
                "Prioritize qualified accounts and improve targeting."
            )

        else:
            recommendations.append(
                "Overall lead quality is low. "
                "Review targeting and lead sources."
            )

        if report["total_leads"] == 0:
            recommendations.append(
                "No leads were analyzed during this period."
            )

        return {
            "period": report["period"],
            "overview": {
                "total_leads": report["total_leads"],
                "hot_leads": report["hot_leads"],
                "warm_leads": report["warm_leads"],
                "cold_leads": report["cold_leads"],
                "average_lead_score": report[
                    "average_lead_score"
                ],
            },
            "top_leads": report["top_leads"],
            "recommendations": recommendations,
        }
