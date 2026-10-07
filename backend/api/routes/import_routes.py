from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from backend.api.dependencies.auth import get_current_session
from backend.api.dependencies.organization import AuthorizedOrganizationContext, require_authorized_csrf
from backend.database.dependencies import get_db
from backend.models.auth_session import AuthSession
from backend.schemas.import_schema import ImportPreview, ImportResult
from backend.services.lead_import_service import ImportValidationError, LeadImportService, MAX_FILE_BYTES


router = APIRouter(prefix="/api/imports/leads", tags=["Imports"])


async def _read_csv(request: Request) -> bytes:
    if request.headers.get("content-type", "").split(";")[0].strip().lower() != "text/csv":
        raise HTTPException(status_code=415, detail="Upload a UTF-8 CSV file (text/csv).")
    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > MAX_FILE_BYTES:
            raise HTTPException(status_code=413, detail="CSV file exceeds the 1 MB limit.")
    return bytes(content)


@router.post("/preview", response_model=ImportPreview)
async def preview_import(
    request: Request,
    context: AuthorizedOrganizationContext = Depends(require_authorized_csrf),
    session: AuthSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    try:
        return LeadImportService(db).preview(
            await _read_csv(request), context.organization.id, context.user.id, session.csrf_token_hash,
        )
    except ImportValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/confirm", response_model=ImportResult)
async def confirm_import(
    request: Request,
    preview_token: str = Header(alias="X-Import-Preview-Token", min_length=1, max_length=512),
    context: AuthorizedOrganizationContext = Depends(require_authorized_csrf),
    session: AuthSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    try:
        return LeadImportService(db).confirm(
            await _read_csv(request), preview_token,
            context.organization.id, context.user.id, session.csrf_token_hash,
        )
    except ImportValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
