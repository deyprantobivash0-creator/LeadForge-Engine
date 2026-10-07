"""Authorize an explicit organization selector for an authenticated user."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.core.exceptions import LeadForgeException
from backend.models.organization import Organization
from backend.models.organization_membership import OrganizationMembership
from backend.models.user import User
from backend.repositories.organization_membership_repository import OrganizationMembershipRepository


@dataclass(frozen=True)
class AuthorizedOrganizationContext:
    user: User
    membership: OrganizationMembership
    organization: Organization


class OrganizationAccessDenied(LeadForgeException):
    status_code = 403
    error_code = "ORGANIZATION_ACCESS_DENIED"

    def __init__(self):
        super().__init__("Organization access denied.")


class OrganizationAuthorizationService:
    def __init__(self, db: Session):
        self.repository = OrganizationMembershipRepository(db)

    def authorize(self, user: User, organization_id: int) -> AuthorizedOrganizationContext:
        membership = self.repository.get_active_membership(user.id, organization_id)
        if membership is None:
            from backend.core.logger import event
            import logging
            event("tenant.access.denied", level=logging.WARNING, user_id=user.id, organization_id=organization_id)
            raise OrganizationAccessDenied()
        return AuthorizedOrganizationContext(
            user=user,
            membership=membership,
            organization=membership.organization,
        )
