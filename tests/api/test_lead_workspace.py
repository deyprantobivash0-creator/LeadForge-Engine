"""Tenant-safe filters and latest-analysis list projection for the Lead workspace."""

from datetime import datetime, timedelta, timezone

from backend.database.session import SessionLocal
from backend.models import Lead, LeadAnalysis


def test_workspace_filters_before_pagination_and_projects_current_analysis(tenant_workspace):
    workspace = tenant_workspace
    client = workspace["clients"]["a"]
    org_a = workspace["ids"]["organizations"]["a"]
    org_b = workspace["ids"]["organizations"]["b"]
    headers = {"X-Organization-ID": str(org_a)}
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with SessionLocal() as db:
        first_id = workspace["ids"]["leads"]["a"]
        db.add(LeadAnalysis(
            organization_id=org_a, lead_id=first_id,
            company="Alpha Company", email="alpha-lead@example.com",
            priority="Warm", lead_score=68, result={}, created_at=now + timedelta(days=1),
        ))
        warm = Lead(
            organization_id=org_a, company="Warm Prospect", email="warm@example.com",
            source="Referral", status="Qualified", processing_status="failed",
        )
        cold = Lead(
            organization_id=org_a, company="Cold Prospect", email="cold@example.com",
            source="Web", status="Contacted", processing_status="completed",
        )
        unanalyzed = Lead(
            organization_id=org_a, company="Unanalyzed Prospect", email="new@example.com",
            source="Referral", status="New", processing_status="pending",
            lead_score=99, priority="Hot",  # stale scalar fields must not become current analysis
        )
        other = Lead(
            organization_id=org_b, company="Other Hot", email="other-hot@example.com",
            source="Referral", status="Qualified", processing_status="failed",
        )
        db.add_all([warm, cold, unanalyzed, other])
        db.flush()
        db.add_all([
            LeadAnalysis(organization_id=org_a, lead_id=warm.id, company=warm.company,
                         email=warm.email, priority="Hot", lead_score=91, result={}, created_at=now),
            LeadAnalysis(organization_id=org_a, lead_id=cold.id, company=cold.company,
                         email=cold.email, priority="Cold", lead_score=12, result={}, created_at=now),
            LeadAnalysis(organization_id=org_b, lead_id=other.id, company=other.company,
                         email=other.email, priority="Hot", lead_score=99, result={}, created_at=now),
        ])
        db.commit()

    listing = client.get("/api/leads/", headers=headers)
    assert listing.status_code == 200
    by_company = {item["company"]: item for item in listing.json()["items"]}
    assert listing.json()["total"] == 4
    assert by_company["Alpha Company"]["current_analysis"]["lead_score"] == 68
    assert by_company["Alpha Company"]["current_analysis"]["priority"] == "Warm"
    assert by_company["Unanalyzed Prospect"]["current_analysis"] is None
    assert "Other Hot" not in by_company

    hot = client.get("/api/leads/", params={"priority": "Hot", "page_size": 1}, headers=headers)
    assert hot.status_code == 200
    assert hot.json()["total"] == 1 and hot.json()["pages"] == 1
    assert [item["company"] for item in hot.json()["items"]] == ["Warm Prospect"]
    assert client.get("/api/leads/", params={"priority": "Hot", "page": 2, "page_size": 1}, headers=headers).json()["items"] == []

    combined = client.get("/api/leads/", params={
        "status": "Qualified", "priority": "Hot", "processing_status": "failed", "source": "refer",
    }, headers=headers)
    assert combined.status_code == 200 and combined.json()["total"] == 1
    assert combined.json()["items"][0]["company"] == "Warm Prospect"

    pending = client.get("/api/leads/", params={"analysis_state": "unanalyzed"}, headers=headers)
    assert pending.status_code == 200
    assert [item["company"] for item in pending.json()["items"]] == ["Unanalyzed Prospect"]

    second_page = client.get("/api/leads/", params={
        "analysis_state": "analyzed", "page_size": 2, "page": 2,
    }, headers=headers)
    assert second_page.status_code == 200
    assert second_page.json()["total"] == 3 and second_page.json()["pages"] == 2
    assert [item["company"] for item in second_page.json()["items"]] == ["Alpha Company"]

    searched = client.get("/api/leads/search", params={
        "company": "Prospect", "priority": "Cold", "page_size": 1,
    }, headers=headers)
    assert searched.status_code == 200 and searched.json()["total"] == 1
    assert searched.json()["items"][0]["company"] == "Cold Prospect"
    assert client.get("/api/leads/search", params={"email": "WARM@EXAMPLE.COM"}, headers=headers).json()["total"] == 1


def test_workspace_rejects_invalid_filter_values(tenant_workspace):
    client = tenant_workspace["clients"]["a"]
    headers = {"X-Organization-ID": str(tenant_workspace["ids"]["organizations"]["a"])}
    for parameter, value in [
        ("status", "Converted"), ("priority", "High"),
        ("processing_status", "running"), ("analysis_state", "unknown"),
    ]:
        response = client.get("/api/leads/", params={parameter: value}, headers=headers)
        assert response.status_code == 422
