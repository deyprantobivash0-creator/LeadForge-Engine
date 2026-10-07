"""Explicit, idempotent development account setup; run only after migrations."""

import argparse
import getpass

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.core.passwords import hash_password, verify_password
from backend.models.organization import Organization
from backend.models.organization_membership import OrganizationMembership
from backend.models.user import User


def bootstrap(db: Session, email: str, password: str) -> tuple[User, Organization]:
    if settings.ENVIRONMENT.lower() != "development":
        raise RuntimeError("Development bootstrap requires ENVIRONMENT=development")
    normalized_email = email.strip().lower()
    if not normalized_email or not password:
        raise ValueError("Email and password are required")

    user = db.scalar(select(User).where(User.email == normalized_email))
    organization = db.scalar(select(Organization).where(Organization.slug == "leadforge-dev"))
    if user and not user.is_active:
        raise ValueError("Existing user is inactive")
    if user and not verify_password(password, user.password_hash):
        raise ValueError("Existing user password does not match; bootstrap does not reset passwords")
    if organization and not organization.is_active:
        raise ValueError("Development organization is inactive")
    if user is None:
        user = User(email=normalized_email, password_hash=hash_password(password))
        db.add(user)
    if organization is None:
        organization = Organization(name="LeadForge Development", slug="leadforge-dev")
        db.add(organization)
    db.flush()

    membership = db.scalar(select(OrganizationMembership).where(
        OrganizationMembership.user_id == user.id,
        OrganizationMembership.organization_id == organization.id,
    ))
    if membership is None:
        db.add(OrganizationMembership(user_id=user.id, organization_id=organization.id, role="owner"))
    elif not membership.is_active:
        raise ValueError("Existing membership is inactive")
    db.commit()
    return user, organization


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a development user and workspace after migration")
    parser.add_argument("--database-url", required=True, help="Explicit development database URL")
    parser.add_argument("--email", required=True)
    args = parser.parse_args()
    if settings.ENVIRONMENT.lower() != "development":
        parser.error("Refusing to run outside ENVIRONMENT=development")
    if not args.database_url.startswith("sqlite:///"):
        parser.error("Development bootstrap only accepts an explicit SQLite URL")
    password = getpass.getpass("Development password: ")
    engine = create_engine(args.database_url)
    try:
        with Session(engine) as db:
            user, organization = bootstrap(db, args.email, password)
            print(f"Development account ready: {user.email} in {organization.slug}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
