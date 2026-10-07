"""Authorized workspace discovery against disposable two-tenant fixtures."""

from backend.database.session import SessionLocal
from backend.models import Organization, OrganizationMembership


def test_workspace_list_requires_session(client):
    assert client.get("/api/organizations").status_code == 401


def test_workspace_list_is_user_scoped(tenant_workspace):
    clients = tenant_workspace["clients"]
    ids = tenant_workspace["ids"]["organizations"]
    assert [row["id"] for row in clients["a"].get("/api/organizations").json()] == [ids["a"]]
    assert [row["id"] for row in clients["b"].get("/api/organizations").json()] == [ids["b"]]
    option = clients["a"].get("/api/organizations").json()[0]
    assert set(option) == {"id", "name", "slug", "role"}


def test_workspace_list_multi_membership_and_inactive_filters(tenant_workspace):
    ids = tenant_workspace["ids"]
    with SessionLocal() as db:
        db.add(OrganizationMembership(user_id=ids["users"]["admin"], organization_id=ids["organizations"]["b"], role="member"))
        db.commit()
    client = tenant_workspace["clients"]["admin"]
    assert {row["id"] for row in client.get("/api/organizations").json()} == set(ids["organizations"].values())
    with SessionLocal() as db:
        db.query(OrganizationMembership).filter_by(user_id=ids["users"]["admin"], organization_id=ids["organizations"]["b"]).one().is_active = False
        db.commit()
    assert [row["id"] for row in client.get("/api/organizations").json()] == [ids["organizations"]["a"]]
    with SessionLocal() as db:
        db.get(Organization, ids["organizations"]["a"]).is_active = False
        db.commit()
    assert client.get("/api/organizations").json() == []
