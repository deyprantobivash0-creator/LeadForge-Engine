import pytest
from backend.core.config import settings

READS = ["/api/leads/", "/api/leads/search", "/api/leads/follow-ups",
         "/api/dashboard/overview", "/api/dashboard/v2/overview",
         "/api/reports/daily", "/api/reports/weekly", "/api/reports/monthly", "/api/reports/v2/overview",
         "/api/reports/executive", "/api/reports/v2/export.csv", "/api/settings/overview"]


@pytest.mark.parametrize("tenant,other", [("a", "b"), ("b", "a")])
def test_registered_customer_route_matrix(tenant_workspace, tenant, other):
    workspace = tenant_workspace
    client = workspace["clients"][tenant]
    own = {"X-Organization-ID": str(workspace["ids"]["organizations"][tenant])}
    foreign = {"X-Organization-ID": str(workspace["ids"]["organizations"][other])}
    foreign_id = workspace["ids"]["leads"][other]
    for path in READS:
        assert client.get(path, headers=foreign).status_code == 403, path
        response = client.get(path, headers=own)
        assert response.status_code == 200, path
        assert ("Beta Company" if tenant == "a" else "Alpha Company") not in response.text
        assert response.headers["cache-control"] == "no-store"
    for suffix in ["", "/intelligence", "/analyses"]:
        assert client.get(f"/api/leads/{foreign_id}{suffix}", headers=own).status_code == 404
    own[settings.CSRF_HEADER_NAME] = client.cookies[settings.CSRF_COOKIE_NAME]
    assert client.post(f"/api/leads/{foreign_id}/process", headers=own).status_code == 404
    assert client.patch(f"/api/leads/{foreign_id}/lifecycle", json={"status": "Lost"}, headers=own).status_code == 404


def test_all_writes_reject_cross_session_csrf(tenant_workspace):
    workspace = tenant_workspace
    client = workspace["clients"]["a"]
    header = {"X-Organization-ID": str(workspace["ids"]["organizations"]["a"]),
              settings.CSRF_HEADER_NAME: workspace["clients"]["b"].cookies[settings.CSRF_COOKIE_NAME]}
    lead = workspace["ids"]["leads"]["a"]
    for method, path, body in [
        ("POST", "/api/auth/logout", None),
        ("POST", "/api/leads/", {"company": "safe", "email": "safe@example.com", "source": "fixture"}),
        ("PATCH", f"/api/leads/{lead}/lifecycle", {"notes": "safe"}),
        ("POST", f"/api/leads/{lead}/process", None),
        ("POST", "/api/imports/leads/preview", None),
        ("POST", "/api/imports/leads/confirm", None),
    ]:
        result = client.request(method, path, json=body, headers={**header, "X-Import-Preview-Token": "invalid"})
        assert result.status_code == 403, path


def test_lifecycle_internal_fields_cannot_be_assigned(tenant_workspace):
    workspace = tenant_workspace
    client = workspace["clients"]["a"]
    header = {"X-Organization-ID": str(workspace["ids"]["organizations"]["a"]),
              settings.CSRF_HEADER_NAME: client.cookies[settings.CSRF_COOKIE_NAME]}
    lead = workspace["ids"]["leads"]["a"]
    for field in ["organization_id", "id", "processing_status", "lead_score", "created_at"]:
        assert client.patch(f"/api/leads/{lead}/lifecycle", json={field: 2}, headers=header).status_code == 422
    for params in [{"company": "x"*201}, {"email": "x"*255}, {"page": 10**100}, {"page_size": 101}]:
        assert client.get("/api/leads/search", params=params, headers=header).status_code == 422
    assert client.patch(f"/api/leads/{lead}/lifecycle", json={"notes": "bad\x00text"}, headers=header).status_code == 422
    assert client.post("/api/leads/", json={"company": "bad\x00text", "email": "safe@example.com", "source": "fixture"}, headers=header).status_code == 422
    for bad_id in [0, -1, 2**63, 10**100]:
        assert client.get(f"/api/leads/{bad_id}", headers=header).status_code == 422


def test_sql_payloads_stay_bound_and_tenant_scoped(tenant_workspace):
    workspace = tenant_workspace
    client = workspace["clients"]["a"]
    headers = {"X-Organization-ID": str(workspace["ids"]["organizations"]["a"])}
    for field in ["company", "email", "source"]:
        response = client.get("/api/leads/search", params={field: "' OR 1=1; DROP TABLE leads; --"}, headers=headers)
        assert response.status_code == 200 and response.json()["total"] == 0
    response = client.get("/api/leads/search", params={"company": "%"}, headers=headers)
    assert response.status_code == 200 and response.json()["total"] == 1
    assert response.json()["items"][0]["company"] == "Alpha Company"
