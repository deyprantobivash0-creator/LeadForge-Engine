from sqlalchemy.orm import Session

from backend.models.organization import Organization


DEFAULT_ORGANIZATION_SLUG = "leadforge-dev"


def get_or_create_default_organization(
    db: Session,
) -> Organization:
    organization = (
        db.query(Organization)
        .filter(
            Organization.slug == DEFAULT_ORGANIZATION_SLUG
        )
        .first()
    )

    if organization:
        return organization

    organization = Organization(
        name="LeadForge Development",
        slug=DEFAULT_ORGANIZATION_SLUG,
        plan="standard",
        monthly_lead_limit=500,
        is_active=True,
    )

    db.add(organization)
    db.commit()
    db.refresh(organization)

    return organization