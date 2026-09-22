from fastapi import APIRouter, Depends,Query
from sqlalchemy.orm import Session

from backend.database.dependencies import get_db
from backend.reports.report_service import ReportService
from backend.schemas.report_schema import (
    ReportResponse,
    ExecutiveReportResponse,
)
from fastapi import APIRouter, Depends, Query
router = APIRouter(
    prefix="/api/reports",
    tags=["Reports"],
)
from typing import Literal

@router.get(
    "/daily",
    response_model=ReportResponse,
)
def daily_report(
    limit: int = Query(
        default=5,
        ge=1,
        le=20,
        description="Number of top leads to return",
    ),
    priority: Literal["Hot", "Warm", "Cold"] | None = Query(
        default=None,
        description="Filter leads by priority",
    ),
    db: Session = Depends(get_db),
):
    service = ReportService(db)

    report = service.daily_report()

    if priority:
        report["top_leads"] = [
            lead
            for lead in report["top_leads"]
            if lead["priority"] == priority
        ]

    report["top_leads"] = report["top_leads"][:limit]

    return report

@router.get(
    "/weekly",
    response_model=ReportResponse,
)
def weekly_report(
    limit: int = Query(
        default=5,
        ge=1,
        le=20,
        description="Number of top leads to return",
    ),
    priority: Literal["Hot", "Warm", "Cold"] | None = Query(
        default=None,
        description="Filter leads by priority",
    ),
    db: Session = Depends(get_db),
):
    service = ReportService(db)

    report = service.weekly_report()

    if priority:
        report["top_leads"] = [
            lead
            for lead in report["top_leads"]
            if lead["priority"] == priority
        ]

    report["top_leads"] = report["top_leads"][:limit]

    return report

@router.get(
    "/monthly",
    response_model=ReportResponse,
)
def monthly_report(
    limit: int = Query(
        default=5,
        ge=1,
        le=20,
        description="Number of top leads to return",
    ),
    priority: Literal["Hot", "Warm", "Cold"] | None = Query(
        default=None,
        description="Filter leads by priority",
    ),
    db: Session = Depends(get_db),
):
    service = ReportService(db)

    report = service.monthly_report()

    if priority:
        report["top_leads"] = [
            lead
            for lead in report["top_leads"]
            if lead["priority"] == priority
        ]

    report["top_leads"] = report["top_leads"][:limit]

    return report

@router.get(
    "/executive",
    response_model=ExecutiveReportResponse,
)
def executive_report(
    db: Session = Depends(get_db),
):
    service = ReportService(db)

    return service.executive_report()