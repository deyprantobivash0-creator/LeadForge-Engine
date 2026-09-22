from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.database.dependencies import get_db
from backend.dashboard.dashboard_service import DashboardService
from backend.schemas.dashboard_schema import (
    DashboardOverviewResponse,
)


router = APIRouter(
    prefix="/api/dashboard",
    tags=["Dashboard"],
)


@router.get(
    "/overview",
    response_model=DashboardOverviewResponse,
)
def dashboard_overview(
    limit: int = Query(
        default=5,
        ge=1,
        le=20,
        description="Number of top opportunities and recent analyses to return",
    ),
    priority: Literal["Hot", "Warm", "Cold"] | None = Query(
        default=None,
        description="Filter dashboard leads by priority",
    ),
    db: Session = Depends(get_db),
):
    service = DashboardService(db)

    dashboard = service.overview()

    if priority:
        dashboard["top_opportunities"] = [
            lead
            for lead in dashboard["top_opportunities"]
            if lead["priority"] == priority
        ]

        dashboard["recent_analyses"] = [
            lead
            for lead in dashboard["recent_analyses"]
            if lead["priority"] == priority
        ]

    dashboard["top_opportunities"] = (
        dashboard["top_opportunities"][:limit]
    )

    dashboard["recent_analyses"] = (
        dashboard["recent_analyses"][:limit]
    )

    return dashboard