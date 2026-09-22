from datetime import datetime

from pydantic import BaseModel


class TopLead(BaseModel):
    id: int
    company: str
    email: str
    priority: str
    lead_score: int


class ReportResponse(BaseModel):
    period: str
    start_date: datetime
    end_date: datetime

    total_leads: int
    hot_leads: int
    warm_leads: int
    cold_leads: int

    average_lead_score: float

    top_leads: list[TopLead]


class ReportOverview(BaseModel):
    total_leads: int
    hot_leads: int
    warm_leads: int
    cold_leads: int
    average_lead_score: float


class ExecutiveReportResponse(BaseModel):
    period: str
    overview: ReportOverview
    top_leads: list[TopLead]
    recommendations: list[str]