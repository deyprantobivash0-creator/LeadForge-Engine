from backend.schemas.decision_evaluation import DecisionEvaluation, EvaluationPage
from backend.services.decision_evaluation_service import DecisionEvaluationService
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, HTTPException
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


@router.get("/decision-evaluation", response_model=DecisionEvaluation)
def decision_evaluation(request: Request, db: Session = Depends(get_db),
                        context: AuthorizedOrganizationContext = Depends(get_current_organization)):
    if request.query_params:
        raise HTTPException(status_code=422, detail="Evaluation supports all time without filters")
    return DecisionEvaluationService(db).summary(context.organization.id)


@router.get("/decision-evaluation/evidence", response_model=EvaluationPage)
def decision_evaluation_evidence(request: Request, limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=100000000), db: Session = Depends(get_db),
    context: AuthorizedOrganizationContext = Depends(get_current_organization)):
    if set(request.query_params) - {"limit", "offset"}:
        raise HTTPException(status_code=422, detail="Unsupported evaluation filter")
    return DecisionEvaluationService(db).page(context.organization.id, limit, offset)
