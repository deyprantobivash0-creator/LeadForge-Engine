"""Fresh scalar authority lookup, with no ORM identity-map role cache or commits."""

from sqlalchemy import select

from backend.models.organization import Organization
from backend.models.organization_membership import OrganizationMembership
from backend.models.user import User


class PermissionRepository:
    def __init__(self, db):
        self.db = db

    def active_role(self, user_id: int, organization_id: int) -> str | None:
        return self.db.scalar(select(OrganizationMembership.role).join(
            User, User.id == OrganizationMembership.user_id,
        ).join(Organization, Organization.id == OrganizationMembership.organization_id).where(
            User.id == user_id, User.is_active.is_(True),
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.is_active.is_(True), Organization.is_active.is_(True),
        ))
