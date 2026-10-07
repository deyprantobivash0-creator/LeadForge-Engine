"""Registered dashboard/report contracts over authorized, mixed-tenant data."""

from datetime import timedelta

import pytest
from sqlalchemy import select

from backend.database.session import SessionLocal
from backend.models import Organization, OrganizationMembership
from backend.reports.report_service import ReportService


def org_headers(workspace, tenant):
    return {"X-Organization-ID": str(workspace["ids"]["organizations"][tenant])}


@pytest.mark.parametrize("tenant,history_total,priority,score,company", [
    ("a", 4, "Hot", 80, "Alpha Company"),
    ("b", 3, "Cold", 20, "Beta Company"),
])
def test_dashboard_metrics_and_rankings_are_tenant_scoped(analytics_workspace, tenant, history_total, priority, score, company):
    workspace = analytics_workspace
    response = workspace["clients"][tenant].get("/api/dashboard/v2/overview", headers=org_headers(workspace, tenant))
    assert response.status_code == 200
    data = response.json()
    assert data["pipeline"] == {
        "total_leads": 1, "analyzed_leads": 1, "unanalyzed_leads": 0,
        "average_current_score": score,
    }
    assert data["priority_distribution"][priority] == 1
    assert [row["company"] for row in data["top_opportunities"]] == [company]
    assert len(data["recent_analysis_activity"]) == history_total
    assert all(("Alpha" in row["company"] or row["company"] == "Shared Alpha") if tenant == "a" else ("Beta" in row["company"] or row["company"] == "Shared Beta") for row in data["recent_analysis_activity"])


def test_dashboard_limit_priority_and_multimembership(analytics_workspace):
    workspace = analytics_workspace
    client = workspace["clients"]["a"]
    filtered = client.get("/api/dashboard/v2/overview", params={"limit": 1, "priority": "Warm"}, headers=org_headers(workspace, "a"))
    assert filtered.status_code == 200
    assert filtered.json()["top_opportunities"] == []
    assert [row["company"] for row in filtered.json()["recent_analysis_activity"]] == ["Shared Alpha"]
    assert filtered.json()["pipeline"]["total_leads"] == 1  # Priority filters lists, not the snapshot.

    with SessionLocal() as db:
        db.add(OrganizationMembership(user_id=workspace["ids"]["users"]["a"], organization_id=workspace["ids"]["organizations"]["b"], role="member"))
        db.commit()
    selected_b = client.get("/api/dashboard/v2/overview", headers=org_headers(workspace, "b"))
    assert selected_b.status_code == 200
    assert selected_b.json()["pipeline"]["total_leads"] == 1
    assert selected_b.json()["top_opportunities"][0]["company"] == "Beta Company"


@pytest.mark.parametrize("path,period", [
    ("/api/reports/daily", "daily"),
    ("/api/reports/weekly", "weekly"),
    ("/api/reports/monthly", "monthly"),
])
@pytest.mark.parametrize("tenant,total,average,first", [
    ("a", 4, 47.5, "Alpha Company"),
    ("b", 3, 71.33, "Beta Highest"),
])
def test_period_reports_are_tenant_scoped(analytics_workspace, path, period, tenant, total, average, first):
    workspace = analytics_workspace
    response = workspace["clients"][tenant].get(path, headers=org_headers(workspace, tenant))
    assert response.status_code == 200
    data = response.json()
    assert data["period"] == period
    assert data["total_leads"] == total
    assert data["average_lead_score"] == average
    assert data["top_leads"][0]["company"] == first
    assert len(data["top_leads"]) == total
    assert {row["email"] for row in data["top_leads"] if row["email"] == "shared@example.com"} == {"shared@example.com"}
    assert "Shared Beta" not in response.text if tenant == "a" else "Shared Alpha" not in response.text


@pytest.mark.parametrize("tenant,expected", [("a", "Shared Alpha"), ("b", "Shared Beta")])
def test_report_priority_and_limit_apply_after_tenant_scope(analytics_workspace, tenant, expected):
    workspace = analytics_workspace
    response = workspace["clients"][tenant].get(
        "/api/reports/monthly",
        params={"priority": "Warm", "limit": 1},
        headers=org_headers(workspace, tenant),
    )
    assert response.status_code == 200
    assert [row["company"] for row in response.json()["top_leads"]] == [expected]
    assert response.json()["total_leads"] == (4 if tenant == "a" else 3)


@pytest.mark.parametrize("tenant,total,first", [("a", 4, "Alpha Company"), ("b", 3, "Beta Highest")])
def test_executive_report_uses_scoped_monthly_report(analytics_workspace, tenant, total, first):
    workspace = analytics_workspace
    response = workspace["clients"][tenant].get("/api/reports/executive", headers=org_headers(workspace, tenant))
    assert response.status_code == 200
    data = response.json()
    assert set(data) == {"period", "overview", "top_leads", "recommendations"}
    assert data["period"] == "monthly"
    assert data["overview"]["total_leads"] == total
    assert data["top_leads"][0]["company"] == first
    assert data["recommendations"]
    assert "Shared Beta" not in response.text if tenant == "a" else "Shared Alpha" not in response.text


def test_empty_organization_is_stable(analytics_workspace):
    workspace = analytics_workspace
    client = workspace["clients"]["a"]
    headers = org_headers(workspace, "empty")
    dashboard = client.get("/api/dashboard/v2/overview", headers=headers)
    report = client.get("/api/reports/monthly", headers=headers)
    executive = client.get("/api/reports/executive", headers=headers)
    assert dashboard.status_code == report.status_code == executive.status_code == 200
    assert dashboard.json()["pipeline"] == {
        "total_leads": 0, "analyzed_leads": 0, "unanalyzed_leads": 0,
        "average_current_score": None,
    }
    assert dashboard.json()["top_opportunities"] == dashboard.json()["recent_analysis_activity"] == []
    assert report.json()["total_leads"] == 0 and report.json()["top_leads"] == []
    assert executive.json()["overview"]["total_leads"] == 0


def test_analytics_rejects_inactive_membership_and_organization(analytics_workspace):
    workspace = analytics_workspace
    client = workspace["clients"]["a"]
    org_id = workspace["ids"]["organizations"]["a"]
    with SessionLocal() as db:
        membership = db.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == workspace["ids"]["users"]["a"], OrganizationMembership.organization_id == org_id))
        membership.is_active = False
        db.commit()
        membership_id = membership.id
    assert client.get("/api/dashboard/v2/overview", headers=org_headers(workspace, "a")).status_code == 403
    with SessionLocal() as db:
        db.get(OrganizationMembership, membership_id).is_active = True
        db.get(Organization, org_id).is_active = False
        db.commit()
    assert client.get("/api/reports/monthly", headers=org_headers(workspace, "a")).status_code == 403


def test_report_range_validation_and_limits(analytics_workspace):
    workspace = analytics_workspace
    client = workspace["clients"]["a"]
    headers = org_headers(workspace, "a")
    assert client.get("/api/dashboard/v2/overview", params={"limit": 0}, headers=headers).status_code == 422
    assert client.get("/api/reports/monthly", params={"limit": 21}, headers=headers).status_code == 422
    assert client.get("/api/reports/monthly", params={"priority": "High"}, headers=headers).status_code == 422
    with SessionLocal() as db:
        service = ReportService(db)
        now = workspace["analytics_now"]
        with pytest.raises(ValueError):
            service.generate_report(workspace["ids"]["organizations"]["a"], now, now - timedelta(days=1), "invalid")


def test_legacy_dashboard_overview_keeps_historical_contract(analytics_workspace):
    workspace = analytics_workspace
    response = workspace["clients"]["a"].get("/api/dashboard/overview", headers=org_headers(workspace, "a"))
    assert response.status_code == 200
    assert response.json()["total_leads"] == 4  # Legacy field means analysis rows.
    assert len(response.json()["recent_analyses"]) == 4
