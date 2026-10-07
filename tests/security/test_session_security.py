from argon2 import PasswordHasher, Type
from fastapi.testclient import TestClient
from sqlalchemy import select
from backend.core.config import settings
from backend.core.passwords import needs_rehash, verify_password
from backend.database.session import SessionLocal
from backend.models import User
from backend.main import app


def test_login_prevents_fixation_and_upgrades_hash(tenant_workspace):
    workspace = tenant_workspace
    client = workspace["clients"]["a"]
    password = "tenant fixture password"
    with SessionLocal() as db:
        user = db.get(User, workspace["ids"]["users"]["a"])
        user.password_hash = PasswordHasher(type=Type.ID, time_cost=1, memory_cost=8192).hash(password)
        db.commit()
    previous = client.cookies[settings.SESSION_COOKIE_NAME]
    csrf = client.cookies[settings.CSRF_COOKIE_NAME]
    assert client.post("/api/auth/login", json={"email": "user-a@example.com", "password": password}).status_code == 200
    assert client.cookies[settings.SESSION_COOKIE_NAME] != previous
    assert client.cookies[settings.CSRF_COOKIE_NAME] != csrf
    with SessionLocal() as db:
        hashed = db.scalar(select(User).where(User.email == "user-a@example.com")).password_hash
        assert verify_password(password, hashed) and not needs_rehash(hashed)
    with TestClient(app, base_url="https://testserver") as attacker:
        attacker.cookies.set(settings.SESSION_COOKIE_NAME, "attacker-chosen-session")
        assert attacker.get("/api/auth/me").status_code == 401
