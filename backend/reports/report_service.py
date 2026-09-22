from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from backend.repositories.lead_analysis_repository import (
    LeadAnalysisRepository,
)


class ReportService:

    from datetime import datetime, timedelta

    def __init__(self, db: Session):
        self.db = db
        self.repository = LeadAnalysisRepository()

    def generate_report(
        self,
        start_date: datetime,
        end_date: datetime,
        period: str,
    ) -> dict:

        analyses = self.repository.get_between_dates(
            self.db,
            start_date,
            end_date,
        )

        total_leads = len(analyses)

        hot_leads = sum(
            1
            for analysis in analyses
            if analysis.priority == "Hot"
        )

        warm_leads = sum(
            1
            for analysis in analyses
            if analysis.priority == "Warm"
        )

        cold_leads = sum(
            1
            for analysis in analyses
            if analysis.priority == "Cold"
        )

        average_score = round(
            sum(
                analysis.lead_score
                for analysis in analyses
            ) / total_leads,
            2,
        ) if total_leads else 0

        top_leads = sorted(
            analyses,
            key=lambda analysis: analysis.lead_score,
            reverse=True,
        )[:5]

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
            "total_leads": total_leads,
            "hot_leads": hot_leads,
            "warm_leads": warm_leads,
            "cold_leads": cold_leads,
            "average_lead_score": average_score,
            "top_leads": top_leads_data,
        }

    def daily_report(self) -> dict:

        now = datetime.utcnow()

        start_date = datetime(
            now.year,
            now.month,
            now.day,
        )

        end_date = start_date + timedelta(days=1)

        return self.generate_report(
            start_date=start_date,
            end_date=end_date,
            period="daily",
        )

    def weekly_report(self) -> dict:

        now = datetime.utcnow()

        start_date = now - timedelta(days=7)

        return self.generate_report(
            start_date=start_date,
            end_date=now,
            period="weekly",
        )

    def monthly_report(self) -> dict:

        now = datetime.utcnow()

        start_date = now - timedelta(days=30)

        return self.generate_report(
            start_date=start_date,
            end_date=now,
            period="monthly",
        )

    def executive_summary(
        self,
        report: dict,
    ) -> dict:

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