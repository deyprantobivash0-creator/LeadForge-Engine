from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.core.organization import (
    get_or_create_default_organization,
)
from backend.database.dependencies import get_db
from backend.schemas.lead_lifecycle_schema import (
    LeadLifecycleUpdate,
)
from backend.schemas.lead_schema import (
    LeadCreate,
    LeadListResponse,
    LeadResponse,
)
from backend.services.lead_intelligence_service import (
    LeadIntelligenceService,
)
from backend.services.lead_lifecycle_service import (
    LeadLifecycleService,
)
from backend.services.lead_service import LeadService


router = APIRouter(
    prefix="/api/leads",
    tags=["Leads"],
)


@router.post("/", response_model=LeadResponse)
def create_lead(
    lead: LeadCreate,
    db: Session = Depends(get_db),
):
    organization = get_or_create_default_organization(db)

    service = LeadService(db)

    try:
        return service.create_lead(
            company=lead.company,
            email=lead.email,
            source=lead.source,
            organization_id=organization.id,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc


@router.get("/", response_model=LeadListResponse)
def get_leads(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    organization = get_or_create_default_organization(db)

    service = LeadService(db)

    items, total = service.get_leads(
        organization_id=organization.id,
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


@router.get("/search", response_model=LeadListResponse)
def search_leads(
    company: str | None = None,
    email: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    organization = get_or_create_default_organization(db)

    service = LeadService(db)

    items, total = service.search_leads(
        organization_id=organization.id,
        company=company,
        email=email,
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


@router.get("/follow-ups", response_model=LeadListResponse)
def get_follow_up_leads(
    days: int = Query(default=7, ge=1, le=365),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    organization = get_or_create_default_organization(db)

    service = LeadService(db)

    items, total = service.get_follow_up_leads(
        organization_id=organization.id,
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


@router.get("/{lead_id}", response_model=LeadResponse)
def get_lead(
    lead_id: int,
    db: Session = Depends(get_db),
):
    organization = get_or_create_default_organization(db)

    service = LeadService(db)

    result = service.get_lead(
        lead_id=lead_id,
        organization_id=organization.id,
    )

    if not result:
        raise HTTPException(
            status_code=404,
            detail="Lead not found",
        )

    return result


@router.patch("/{lead_id}/lifecycle")
def update_lead_lifecycle(
    lead_id: int,
    payload: LeadLifecycleUpdate,
    db: Session = Depends(get_db),
):
    organization = get_or_create_default_organization(db)

    service = LeadLifecycleService(db)

    try:
        result = service.update_lifecycle(
            lead_id=lead_id,
            organization_id=organization.id,
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


@router.get("/{lead_id}/intelligence")
def get_lead_intelligence(
    lead_id: int,
    db: Session = Depends(get_db),
):
    organization = get_or_create_default_organization(db)

    service = LeadIntelligenceService(db)

    result = service.get_by_id(
        lead_id=lead_id,
        organization_id=organization.id,
    )

    if not result:
        raise HTTPException(
            status_code=404,
            detail="Lead not found",
        )

    return result