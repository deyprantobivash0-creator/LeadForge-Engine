from datetime import datetime

from pydantic import BaseModel


class DashboardLead(BaseModel):
    id: int
    company: str
    email: str
    priority: str
    lead_score: int


class DashboardRecentLead(DashboardLead):
    created_at: datetime


class DashboardOverviewResponse(BaseModel):
    total_leads: int
    hot_leads: int
    warm_leads: int
    cold_leads: int
    average_lead_score: float
    top_opportunities: list[DashboardLead]
    recent_analyses: list[DashboardRecentLead]