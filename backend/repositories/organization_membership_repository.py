"""SQL-scoped membership lookup for request authorization."""

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from backend.models.organization import Organization
from backend.models.organization_membership import OrganizationMembership


class OrganizationMembershipRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_active_membership(self, user_id: int, organization_id: int) -> OrganizationMembership | None:
        return self.db.scalar(
            select(OrganizationMembership)
            .join(Organization, OrganizationMembership.organization_id == Organization.id)
            .options(joinedload(OrganizationMembership.organization))
            .where(
                OrganizationMembership.user_id == user_id,
                OrganizationMembership.organization_id == organization_id,
                OrganizationMembership.is_active.is_(True),
                Organization.is_active.is_(True),
            )
        )

    def list_active_for_user(self, user_id: int) -> list[OrganizationMembership]:
        return list(self.db.scalars(
            select(OrganizationMembership)
            .join(Organization, OrganizationMembership.organization_id == Organization.id)
            .options(joinedload(OrganizationMembership.organization))
            .where(
                OrganizationMembership.user_id == user_id,
                OrganizationMembership.is_active.is_(True),
                Organization.is_active.is_(True),
            )
            .order_by(Organization.name, Organization.id)
        ).all())
