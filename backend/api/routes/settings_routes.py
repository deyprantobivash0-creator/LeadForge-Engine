from fastapi import APIRouter, Depends, Response

from backend.api.dependencies.organization import AuthorizedOrganizationContext, get_current_organization
from backend.schemas.settings_schema import SettingsOverview
from backend.services.settings_service import SettingsService


router = APIRouter(prefix="/api/settings", tags=["Settings"])


@router.get("/overview", response_model=SettingsOverview)
def settings_overview(
    response: Response,
    context: AuthorizedOrganizationContext = Depends(get_current_organization),
):
    response.headers["Cache-Control"] = "no-store"
    return SettingsService.overview(context)
