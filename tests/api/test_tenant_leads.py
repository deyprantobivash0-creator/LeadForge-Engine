"""Two-organization authorization contract for registered customer routes."""

import pytest
from sqlalchemy import select

from backend.core.config import settings
from backend.database.session import SessionLocal
from backend.models import Lead, Organization, OrganizationMembership, User


def headers(workspace, tenant, *, csrf=False, client_key=None):
    result = {"X-Organization-ID": str(workspace["ids"]["organizations"][tenant])}
    if csrf:
        client = workspace["clients"][client_key or tenant]
        result[settings.CSRF_HEADER_NAME] = client.cookies[settings.CSRF_COOKIE_NAME]
    return result


@pytest.mark.parametrize("tenant", ["a", "b"])
def test_legitimate_tenant_lead_flow(tenant_workspace, tenant):
    workspace = tenant_workspace
    client = workspace["clients"][tenant]
    org_headers = headers(workspace, tenant)
    lead_id = workspace["ids"]["leads"][tenant]
    own_company = "Alpha Company" if tenant == "a" else "Beta Company"
    other_company = "Beta Company" if tenant == "a" else "Alpha Company"

    listing = client.get("/api/leads/", headers=org_headers)
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert [item["company"] for item in listing.json()["items"]] == [own_company]
    assert client.get(f"/api/leads/{lead_id}", headers=org_headers).json()["company"] == own_company

    search = client.get("/api/leads/search", params={"company": own_company}, headers=org_headers)
    assert search.status_code == 200 and search.json()["total"] == 1
    hidden_search = client.get("/api/leads/search", params={"company": other_company}, headers=org_headers)
    assert hidden_search.status_code == 200 and hidden_search.json()["total"] == 0

    followups = client.get("/api/leads/follow-ups", headers=org_headers)
    assert followups.status_code == 200
    assert [item["id"] for item in followups.json()["items"]] == [lead_id]

    intelligence = client.get(f"/api/leads/{lead_id}/intelligence", headers=org_headers)
    assert intelligence.status_code == 200
    assert intelligence.json()["analysis"]["result"]["tenant"] == tenant

    created = client.post(
        "/api/leads/",
        json={"company": f"New {tenant}", "email": f"new-{tenant}@example.com", "source": "test"},
        headers=headers(workspace, tenant, csrf=True),
    )
    assert created.status_code == 200
    with SessionLocal() as db:
        assert db.get(Lead, created.json()["id"]).organization_id == workspace["ids"]["organizations"][tenant]

    updated = client.patch(
        f"/api/leads/{lead_id}/lifecycle",
        json={"status": "Qualified"},
        headers=headers(workspace, tenant, csrf=True),
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "Qualified"


@pytest.mark.parametrize("method,path,payload", [
    ("POST", "/api/leads/", {"company": "New", "email": "new@example.com", "source": "test"}),
    ("GET", "/api/leads/", None),
    ("GET", "/api/leads/search", None),
    ("GET", "/api/leads/follow-ups", None),
    ("GET", "/api/leads/1", None),
    ("PATCH", "/api/leads/1/lifecycle", {"status": "Qualified"}),
    ("GET", "/api/leads/1/intelligence", None),
])
def test_every_lead_route_requires_authentication(client, method, path, payload):
    response = client.request(method, path, json=payload, headers={"X-Organization-ID": "1"})
    assert response.status_code == 401


@pytest.mark.parametrize("selector", [None, "abc", "0", "-1", "1.5", "999999999999999999999"])
def test_organization_selector_fails_closed(tenant_workspace, selector):
    client = tenant_workspace["clients"]["a"]
    header = {} if selector is None else {"X-Organization-ID": selector}
    response = client.get("/api/leads/", headers=header)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "ORGANIZATION_SELECTOR_INVALID"


def test_unauthorized_inactive_membership_and_organization(tenant_workspace):
    workspace = tenant_workspace
    client = workspace["clients"]["a"]
    assert client.get("/api/leads/", headers=headers(workspace, "b")).status_code == 403
    with SessionLocal() as db:
        membership = db.scalar(select(OrganizationMembership).where(
            OrganizationMembership.user_id == workspace["ids"]["users"]["a"],
            OrganizationMembership.organization_id == workspace["ids"]["organizations"]["a"],
        ))
        membership_id = membership.id
        membership.is_active = False
        db.commit()
    assert client.get("/api/leads/", headers=headers(workspace, "a")).status_code == 403
    with SessionLocal() as db:
        membership = db.get(OrganizationMembership, membership_id)
        membership.is_active = True
        db.get(Organization, workspace["ids"]["organizations"]["a"]).is_active = False
        db.commit()
    assert client.get("/api/leads/", headers=headers(workspace, "a")).status_code == 403


def test_disabled_user_remains_unauthenticated(tenant_workspace):
    workspace = tenant_workspace
    with SessionLocal() as db:
        db.get(User, workspace["ids"]["users"]["a"]).is_active = False
        db.commit()
    assert workspace["clients"]["a"].get("/api/leads/", headers=headers(workspace, "a")).status_code == 401


@pytest.mark.parametrize("tenant,other", [("a", "b"), ("b", "a")])
def test_cross_tenant_record_ids_are_not_found(tenant_workspace, tenant, other):
    workspace = tenant_workspace
    client = workspace["clients"][tenant]
    foreign_id = workspace["ids"]["leads"][other]
    org_headers = headers(workspace, tenant)
    assert client.get(f"/api/leads/{foreign_id}", headers=org_headers).status_code == 404
    assert client.get(f"/api/leads/{foreign_id}/intelligence", headers=org_headers).status_code == 404
    assert client.patch(
        f"/api/leads/{foreign_id}/lifecycle",
        json={"status": "Lost"},
        headers=headers(workspace, tenant, csrf=True),
    ).status_code == 404
    with SessionLocal() as db:
        assert db.get(Lead, foreign_id).status == "New"


def test_lead_writes_require_session_bound_csrf(tenant_workspace):
    workspace = tenant_workspace
    client = workspace["clients"]["a"]
    org_headers = headers(workspace, "a")
    create = {"company": "Protected", "email": "protected@example.com", "source": "test"}
    assert client.post("/api/leads/", json=create, headers=org_headers).status_code == 403
    assert client.post("/api/leads/", json=create, headers={**org_headers, settings.CSRF_HEADER_NAME: "wrong"}).status_code == 403
    other_csrf = workspace["clients"]["b"].cookies[settings.CSRF_COOKIE_NAME]
    assert client.post("/api/leads/", json=create, headers={**org_headers, settings.CSRF_HEADER_NAME: other_csrf}).status_code == 403
    lead_id = workspace["ids"]["leads"]["a"]
    assert client.patch(f"/api/leads/{lead_id}/lifecycle", json={"status": "Lost"}, headers=org_headers).status_code == 403
    assert client.patch(f"/api/leads/{lead_id}/lifecycle", json={"status": "Lost"}, headers={**org_headers, settings.CSRF_HEADER_NAME: other_csrf}).status_code == 403
    assert client.post("/api/leads/", json=create, headers=headers(workspace, "a", csrf=True)).status_code == 200
    assert client.patch(f"/api/leads/{lead_id}/lifecycle", json={"status": "Qualified"}, headers=headers(workspace, "a", csrf=True)).status_code == 200


def test_client_cannot_choose_lead_ownership_in_body(tenant_workspace):
    workspace = tenant_workspace
    response = workspace["clients"]["a"].post(
        "/api/leads/",
        json={"company": "Injected", "email": "inject@example.com", "source": "test", "organization_id": workspace["ids"]["organizations"]["b"]},
        headers=headers(workspace, "a", csrf=True),
    )
    assert response.status_code == 422
    with SessionLocal() as db:
        assert db.scalar(select(Lead).where(Lead.email == "inject@example.com")) is None


def test_multi_membership_selection_and_roles(tenant_workspace):
    workspace = tenant_workspace
    with SessionLocal() as db:
        db.add(OrganizationMembership(user_id=workspace["ids"]["users"]["a"], organization_id=workspace["ids"]["organizations"]["b"], role="member"))
        db.commit()
    client = workspace["clients"]["a"]
    a = client.get("/api/leads/", headers=headers(workspace, "a"))
    b = client.get("/api/leads/", headers=headers(workspace, "b"))
    assert [item["company"] for item in a.json()["items"]] == ["Alpha Company"]
    assert [item["company"] for item in b.json()["items"]] == ["Beta Company"]
    admin = workspace["clients"]["admin"].get("/api/leads/", headers=headers(workspace, "a"))
    assert admin.status_code == 200 and admin.json()["total"] == 1
    assert workspace["clients"]["b"].get("/api/leads/", headers=headers(workspace, "b")).status_code == 200


def test_no_implicit_default_organization(tenant_workspace):
    workspace = tenant_workspace
    client = workspace["clients"]["a"]
    assert client.get("/api/leads/").status_code == 400
    assert client.get("/api/leads/", headers=headers(workspace, "a")).status_code == 200
    with SessionLocal() as db:
        assert db.scalar(select(Organization).where(Organization.slug == "leadforge-dev")) is None


@pytest.mark.parametrize("path", [
    "/api/dashboard/overview",
    "/api/dashboard/v2/overview",
    "/api/reports/daily",
    "/api/reports/weekly",
    "/api/reports/monthly",
    "/api/reports/executive",
])
def test_analytics_routes_require_authorized_organization(tenant_workspace, client, path):
    workspace = tenant_workspace
    assert client.get(path, headers=headers(workspace, "a")).status_code == 401
    tenant_client = workspace["clients"]["a"]
    assert tenant_client.get(path).status_code == 400
    assert tenant_client.get(path, headers=headers(workspace, "b")).status_code == 403
    response = tenant_client.get(path, headers=headers(workspace, "a"))
    assert response.status_code == 200
    assert "Beta Company" not in response.text


def test_ingestion_route_remains_unregistered(tenant_workspace):
    assert tenant_workspace["clients"]["a"].get("/api/ingestion/jobs").status_code == 404
