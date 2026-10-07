"""Read-only list of workspaces available to the authenticated caller."""

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.api.dependencies.auth import get_current_user
from backend.database.dependencies import get_db
from backend.models.user import User
from backend.repositories.organization_membership_repository import OrganizationMembershipRepository


router = APIRouter(prefix="/api/organizations", tags=["Organizations"])


class OrganizationOption(BaseModel):
    id: int
    name: str
    slug: str
    role: str


@router.get("", response_model=list[OrganizationOption])
def list_organizations(
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    memberships = OrganizationMembershipRepository(db).list_active_for_user(user.id)
    return [
        OrganizationOption(
            id=membership.organization.id,
            name=membership.organization.name,
            slug=membership.organization.slug,
            role=membership.role,
        )
        for membership in memberships
    ]
