from math import ceil
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from backend.api.dependencies.organization import (
    AuthorizedOrganizationContext,
    get_current_organization,
    require_authorized_csrf,
)
from backend.database.dependencies import get_db
from backend.schemas.lead_lifecycle_schema import (
    LeadLifecycleUpdate,
)
from backend.schemas.lead_schema import (
    LeadCreate,
    LeadListResponse,
    LeadResponse,
    LeadIntelligenceResponse,
    AnalysisHistoryResponse,
    LeadDetailResponse,
    LeadProcessingResponse,
)
from backend.schemas.lead_contract import LeadLifecycle, LeadPriority, ProcessingStatus
from backend.repositories.lead_analysis_repository import LeadAnalysisRepository
from backend.services.lead_intelligence_service import (
    LeadIntelligenceService,
)
from backend.services.lead_lifecycle_service import (
    LeadLifecycleService,
)
from backend.services.lead_service import LeadService
from backend.services.lead_processing_service import (
    LeadProcessingService, LeadNotFound, ProcessingConflict, ProcessingFailure,
)


router = APIRouter(
    prefix="/api/leads",
    tags=["Leads"],
)

LeadID = Annotated[int, Path(ge=1, le=9223372036854775807)]


def _list_response(items, total: int, page: int, page_size: int):
    return {
        "items": [
            {
                **LeadResponse.model_validate(lead).model_dump(),
                "current_analysis": (
                    {"id": analysis_id, "lead_score": score, "priority": priority}
                    if analysis_id is not None else None
                ),
            }
            for lead, analysis_id, score, priority in items
        ],
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": ceil(total / page_size) if total else 0,
    }


@router.post("/", response_model=LeadResponse)
def create_lead(
    lead: LeadCreate,
    db: Session = Depends(get_db),
    context: AuthorizedOrganizationContext = Depends(require_authorized_csrf),
):
    service = LeadService(db)

    try:
        return service.create_lead(
            company=lead.company,
            email=lead.email,
            source=lead.source,
            organization_id=context.organization.id,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc


@router.get("/", response_model=LeadListResponse)
def get_leads(
    page: int = Query(default=1, ge=1, le=1000000),
    page_size: int = Query(default=50, ge=1, le=100),
    status: LeadLifecycle | None = None,
    priority: LeadPriority | None = None,
    processing_status: ProcessingStatus | None = None,
    source: str | None = Query(default=None, max_length=100),
    analysis_state: Literal["analyzed", "unanalyzed"] | None = None,
    db: Session = Depends(get_db),
    context: AuthorizedOrganizationContext = Depends(get_current_organization),
):
    service = LeadService(db)

    items, total = service.get_leads(
        organization_id=context.organization.id,
        page=page,
        page_size=page_size,
        status=status,
        priority=priority,
        processing_status=processing_status,
        source=source,
        analysis_state=analysis_state,
    )
    return _list_response(items, total, page, page_size)


@router.get("/search", response_model=LeadListResponse)
def search_leads(
    company: str | None = Query(default=None, max_length=200),
    email: str | None = Query(default=None, max_length=254),
    page: int = Query(default=1, ge=1, le=1000000),
    page_size: int = Query(default=50, ge=1, le=100),
    status: LeadLifecycle | None = None,
    priority: LeadPriority | None = None,
    processing_status: ProcessingStatus | None = None,
    source: str | None = Query(default=None, max_length=100),
    analysis_state: Literal["analyzed", "unanalyzed"] | None = None,
    db: Session = Depends(get_db),
    context: AuthorizedOrganizationContext = Depends(get_current_organization),
):
    service = LeadService(db)

    items, total = service.search_leads(
        organization_id=context.organization.id,
        company=company,
        email=email,
        page=page,
        page_size=page_size,
        status=status,
        priority=priority,
        processing_status=processing_status,
        source=source,
        analysis_state=analysis_state,
    )
    return _list_response(items, total, page, page_size)


@router.get("/follow-ups", response_model=LeadListResponse)
def get_follow_up_leads(
    days: int = Query(default=7, ge=1, le=365),
    page: int = Query(default=1, ge=1, le=1000000),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    context: AuthorizedOrganizationContext = Depends(get_current_organization),
):
    service = LeadService(db)

    items, total = service.get_follow_up_leads(
        organization_id=context.organization.id,
        days=days,
        page=page,
        page_size=page_size,
    )

    pages = ceil(total / page_size) if total else 0

    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": pages,
    }


@router.get("/{lead_id}", response_model=LeadDetailResponse)
def get_lead(
    lead_id: LeadID,
    db: Session = Depends(get_db),
    context: AuthorizedOrganizationContext = Depends(get_current_organization),
):
    service = LeadService(db)

    result = service.get_lead(
        lead_id=lead_id,
        organization_id=context.organization.id,
    )

    if not result:
        raise HTTPException(
            status_code=404,
            detail="Lead not found",
        )

    intelligence = LeadIntelligenceService(db).get_by_id(lead_id, context.organization.id)
    return {**LeadResponse.model_validate(result).model_dump(), "current_analysis": intelligence["analysis"]}


@router.patch("/{lead_id}/lifecycle", response_model=LeadResponse)
def update_lead_lifecycle(
    lead_id: LeadID,
    payload: LeadLifecycleUpdate,
    db: Session = Depends(get_db),
    context: AuthorizedOrganizationContext = Depends(require_authorized_csrf),
):
    service = LeadLifecycleService(db)

    try:
        result = service.update_lifecycle(
            lead_id=lead_id,
            organization_id=context.organization.id,
            status=payload.status,
            notes=payload.notes,
            last_contacted=payload.last_contacted,
            next_follow_up=payload.next_follow_up,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    if not result:
        raise HTTPException(
            status_code=404,
            detail="Lead not found",
        )

    return result


@router.get("/{lead_id}/intelligence", response_model=LeadIntelligenceResponse)
def get_lead_intelligence(
    lead_id: LeadID,
    db: Session = Depends(get_db),
    context: AuthorizedOrganizationContext = Depends(get_current_organization),
):
    service = LeadIntelligenceService(db)

    result = service.get_by_id(
        lead_id=lead_id,
        organization_id=context.organization.id,
    )

    if not result:
        raise HTTPException(
            status_code=404,
            detail="Lead not found",
        )

    return result


@router.get("/{lead_id}/analyses", response_model=AnalysisHistoryResponse)
def get_lead_analysis_history(
    lead_id: LeadID,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=100000000),
    db: Session = Depends(get_db),
    context: AuthorizedOrganizationContext = Depends(get_current_organization),
):
    if LeadService(db).get_lead(lead_id, context.organization.id) is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    items, total = LeadAnalysisRepository().get_history_for_lead(
        db, lead_id, context.organization.id, limit, offset,
    )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.post("/{lead_id}/process", response_model=LeadProcessingResponse)
async def process_lead(
    lead_id: LeadID,
    db: Session = Depends(get_db),
    context: AuthorizedOrganizationContext = Depends(require_authorized_csrf),
):
    try:
        return await LeadProcessingService(db).process(context.organization.id, lead_id)
    except LeadNotFound as exc:
        raise HTTPException(status_code=404, detail="Lead not found") from exc
    except ProcessingConflict as exc:
        raise HTTPException(status_code=409, detail="Lead is already processing") from exc
    except ProcessingFailure as exc:
        status = {
            "provider_not_configured": 503,
            "provider_timeout": 504,
            "provider_unavailable": 503,
            "malformed_provider_output": 502,
            "validation_failure": 502,
        }.get(exc.code, 500)
        raise HTTPException(status_code=status, detail=exc.code) from exc
