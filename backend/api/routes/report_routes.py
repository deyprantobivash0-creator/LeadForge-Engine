from typing import Literal
from datetime import date, timedelta
import csv
import io
import logging
from time import perf_counter
from backend.core.logger import event
from backend.core.csv_security import spreadsheet_cell

from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.database.dependencies import get_db
from backend.api.dependencies.organization import (
    AuthorizedOrganizationContext,
    get_current_organization,
)
from backend.reports.report_service import ReportService
from backend.services.report_v2_service import ReportV2Service
from backend.schemas.report_v2_schema import ReportV2Response
from backend.schemas.report_schema import (
    ReportResponse,
    ExecutiveReportResponse,
)
router = APIRouter(
    prefix="/api/reports",
    tags=["Reports"],
)


def report_window(preset: Literal["today", "7d", "30d", "custom"], start: date | None, end: date | None):
    try:
        return ReportV2Service.window(preset, start, end)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/v2/overview", response_model=ReportV2Response)
def report_v2_overview(
    preset: Literal["today", "7d", "30d", "custom"] = "30d",
    start: date | None = None,
    end: date | None = None,
    db: Session = Depends(get_db),
    context: AuthorizedOrganizationContext = Depends(get_current_organization),
):
    report_window(preset, start, end)
    return ReportV2Service(db).overview(context.organization.id, preset, start, end)


@router.get("/v2/export.csv")
def report_v2_export(
    preset: Literal["today", "7d", "30d", "custom"] = "30d",
    start: date | None = None,
    end: date | None = None,
    db: Session = Depends(get_db),
    context: AuthorizedOrganizationContext = Depends(get_current_organization),
):
    first, last = report_window(preset, start, end)
    organization_id = context.organization.id
    filename = f"leadforge-report-{first.date()}-to-{(last - timedelta(microseconds=1)).date()}.csv"

    def rows():
        started = perf_counter()
        count = 0
        event("report.export.started", organization_id=organization_id)
        try:
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerow(["analysis_id", "lead_id", "company", "email", "score", "priority", "analyzed_at"])
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)
            for row in ReportV2Service(db).repository.export_batches(db, organization_id, first, last):
                # Prefix spreadsheet formula characters to keep downloaded CSV inert.
                safe = [spreadsheet_cell(value) for value in row]
                writer.writerow(safe)
                yield buffer.getvalue()
                buffer.seek(0)
                buffer.truncate(0)
                count += 1
        except Exception as exc:
            event("report.export.failed", level=logging.ERROR, organization_id=organization_id,
                  exception_type=type(exc).__name__, duration_ms=round((perf_counter()-started)*1000, 2))
            raise
        else:
            event("report.export.completed", organization_id=organization_id, rows=count,
                  duration_ms=round((perf_counter()-started)*1000, 2))

    return StreamingResponse(rows(), media_type="text/csv; charset=utf-8", headers={
        "Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"})

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
    context: AuthorizedOrganizationContext = Depends(get_current_organization),
):
    service = ReportService(db)
    return service.daily_report(context.organization.id, limit=limit, priority=priority)

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
    context: AuthorizedOrganizationContext = Depends(get_current_organization),
):
    service = ReportService(db)
    return service.weekly_report(context.organization.id, limit=limit, priority=priority)

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
    context: AuthorizedOrganizationContext = Depends(get_current_organization),
):
    service = ReportService(db)
    return service.monthly_report(context.organization.id, limit=limit, priority=priority)

@router.get(
    "/executive",
    response_model=ExecutiveReportResponse,
)
def executive_report(
    db: Session = Depends(get_db),
    context: AuthorizedOrganizationContext = Depends(get_current_organization),
):
    service = ReportService(db)
    return service.executive_report(context.organization.id)
