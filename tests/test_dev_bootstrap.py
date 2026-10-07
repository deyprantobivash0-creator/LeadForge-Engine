"""Bootstrap operates only on the test fixture's disposable database."""

from sqlalchemy import func, select
import pytest

from backend.database.session import SessionLocal
from backend.models import Organization, OrganizationMembership, User
from backend.core.passwords import verify_password
from backend.core.config import settings
from scripts.bootstrap_dev_user import bootstrap


def test_bootstrap_idempotent_and_hashed(client):
    with SessionLocal() as db:
        user, organization = bootstrap(db, " DEV@EXAMPLE.COM ", "fixture password")
        ids = (user.id, organization.id)
        assert verify_password("fixture password", user.password_hash)
        assert user.password_hash != "fixture password"
        second_user, second_organization = bootstrap(db, "dev@example.com", "fixture password")
        assert (second_user.id, second_organization.id) == ids
        assert db.scalar(select(func.count()).select_from(User)) == 1
        assert db.scalar(select(func.count()).select_from(Organization)) == 1
        assert db.scalar(select(func.count()).select_from(OrganizationMembership)) == 1
        with pytest.raises(ValueError, match="does not match"):
            bootstrap(db, "dev@example.com", "different password")


def test_bootstrap_refuses_non_development(client, monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    with SessionLocal() as db:
        with pytest.raises(RuntimeError, match="development"):
            bootstrap(db, "dev@example.com", "fixture password")
        assert db.scalar(select(func.count()).select_from(User)) == 0
