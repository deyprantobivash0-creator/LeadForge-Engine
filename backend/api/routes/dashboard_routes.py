from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.database.dependencies import get_db
from backend.api.dependencies.organization import (
    AuthorizedOrganizationContext,
    get_current_organization,
)
from backend.dashboard.dashboard_service import DashboardService
from backend.schemas.dashboard_schema import (
    DashboardOverviewResponse,
    LegacyDashboardOverviewResponse,
)


router = APIRouter(
    prefix="/api/dashboard",
    tags=["Dashboard"],
)


@router.get(
    "/overview",
    response_model=LegacyDashboardOverviewResponse,
)
def dashboard_overview(
    limit: int = Query(
        default=5,
        ge=1,
        le=20,
        description="Number of historical analysis rows to return",
    ),
    priority: Literal["Hot", "Warm", "Cold"] | None = Query(
        default=None,
        description="Filter historical top and recent lists; historical summary remains unfiltered",
    ),
    db: Session = Depends(get_db),
    context: AuthorizedOrganizationContext = Depends(get_current_organization),
):
    service = DashboardService(db)
    return service.legacy_overview(context.organization.id, limit=limit, priority=priority)


@router.get("/v2/overview", response_model=DashboardOverviewResponse)
def current_dashboard_overview(
    limit: int = Query(default=5, ge=1, le=20),
    priority: Literal["Hot", "Warm", "Cold"] | None = Query(default=None),
    db: Session = Depends(get_db),
    context: AuthorizedOrganizationContext = Depends(get_current_organization),
):
    return DashboardService(db).current_overview(context.organization.id, limit=limit, priority=priority)
