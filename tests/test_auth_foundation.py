"""Authentication foundation tests use only the disposable pytest database."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.passwords import hash_password, needs_rehash, verify_password
from backend.core.session_tokens import generate_session_token, hash_session_token, verify_session_token
from backend.database.base import Base
from backend.models import AuthSession, Organization, OrganizationMembership, User


@pytest.fixture
def db(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'auth.db').as_posix()}")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            yield session
    finally:
        engine.dispose()


def test_password_and_session_token_crypto():
    password = "a local test password"
    password_hash = hash_password(password)
    assert password_hash != password
    assert password_hash.startswith("$argon2id$")
    assert verify_password(password, password_hash)
    assert not verify_password("wrong", password_hash)
    assert not verify_password(password, "invalid hash")
    assert not needs_rehash(password_hash)

    token = generate_session_token()
    other = generate_session_token()
    assert token != other
    assert len(token) >= 43  # 32 random bytes, URL-safe base64 representation.
    digest = hash_session_token(token)
    assert len(digest) == 64
    assert digest != token
    assert digest == hash_session_token(token)
    assert verify_session_token(token, digest)
    assert not verify_session_token(other, digest)


def test_users_memberships_and_sessions(db):
    password = "another local password"
    user_a = User(email="  A@Example.COM  ", password_hash=hash_password(password))
    user_b = User(email="b@example.com", password_hash=hash_password(password), is_active=False)
    org_a = Organization(name="A", slug="org-a")
    org_b = Organization(name="B", slug="org-b")
    db.add_all([user_a, user_b, org_a, org_b])
    db.commit()

    assert user_a.email == "a@example.com"
    assert user_b.is_active is False
    assert user_a.password_hash != password
    assert password not in str(db.execute(text("SELECT password_hash FROM users WHERE id=:id"), {"id": user_a.id}).scalar_one())

    db.add_all([
        OrganizationMembership(user=user_a, organization=org_a, role="owner"),
        OrganizationMembership(user=user_a, organization=org_b, role="admin", is_active=False),
        OrganizationMembership(user=user_b, organization=org_a),
    ])
    db.commit()
    memberships = db.scalars(select(OrganizationMembership)).all()
    assert {(m.user.email, m.organization.slug, m.role, m.is_active) for m in memberships} == {
        ("a@example.com", "org-a", "owner", True),
        ("a@example.com", "org-b", "admin", False),
        ("b@example.com", "org-a", "member", True),
    }

    token = generate_session_token()
    expires = datetime.utcnow() + timedelta(days=7)
    auth_session = AuthSession(user=user_a, token_hash=hash_session_token(token), csrf_token_hash=hash_session_token(generate_session_token()), expires_at=expires)
    db.add(auth_session)
    db.commit()
    db.refresh(auth_session)
    assert auth_session.user.id == user_a.id
    assert auth_session.token_hash != token
    assert auth_session.expires_at == expires
    assert token not in db.execute(text("SELECT token_hash FROM auth_sessions WHERE id=:id"), {"id": auth_session.id}).scalar_one()
    auth_session.revoked_at = datetime.utcnow()
    db.commit()
    db.refresh(auth_session)
    assert auth_session.revoked_at is not None


def test_database_constraints(db):
    user = User(email="c@example.com", password_hash=hash_password("password"))
    org = Organization(name="A", slug="unique-org")
    db.add_all([user, org])
    db.commit()

    db.add(User(email=" C@EXAMPLE.COM ", password_hash=hash_password("password")))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    db.add(OrganizationMembership(user_id=user.id, organization_id=org.id, role="member"))
    db.commit()
    db.add(OrganizationMembership(user_id=user.id, organization_id=org.id, role="admin"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    second_org = Organization(name="B", slug="second-org")
    db.add(second_org)
    db.commit()
    db.add(OrganizationMembership(user_id=user.id, organization_id=second_org.id, role="invalid"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    digest = hash_session_token(generate_session_token())
    db.add(AuthSession(user_id=user.id, token_hash=digest, csrf_token_hash=hash_session_token(generate_session_token()), expires_at=datetime.utcnow()))
    db.commit()
    db.add(AuthSession(user_id=user.id, token_hash=digest, csrf_token_hash=hash_session_token(generate_session_token()), expires_at=datetime.utcnow()))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    # Deleting an organization through a user relationship must not cascade customer data.
    with pytest.raises(IntegrityError):
        db.execute(text("DELETE FROM organizations WHERE id=:id"), {"id": org.id})
        db.commit()
    db.rollback()
