"""Current Lead snapshot remains distinct from historical analysis activity."""

from datetime import datetime, timedelta

from sqlalchemy import select

from backend.database.session import SessionLocal
from backend.models import Lead, LeadAnalysis, Organization, OrganizationMembership


def _headers(organization_id):
    return {"X-Organization-ID": str(organization_id)}


def test_current_snapshot_uses_one_latest_linked_analysis_per_tenant_lead(tenant_workspace):
    workspace = tenant_workspace
    org_a = workspace["ids"]["organizations"]["a"]
    org_b = workspace["ids"]["organizations"]["b"]
    lead_a = workspace["ids"]["leads"]["a"]
    now = datetime(2026, 10, 3, 12, 0)
    with SessionLocal() as db:
        original = db.get(Lead, lead_a)
        original.status = "Meeting"
        original.processing_status = "completed"
        db.scalar(select(LeadAnalysis).where(LeadAnalysis.lead_id == lead_a)).created_at = now - timedelta(days=1)
        warm = Lead(organization_id=org_a, company="Warm Company", email="warm-dashboard@example.com",
                    source="test", status="Qualified", processing_status="completed")
        cold = Lead(organization_id=org_a, company="Cold Company", email="cold-dashboard@example.com",
                    source="test", status="Contacted", processing_status="failed")
        unanalyzed = Lead(organization_id=org_a, company="Unanalyzed Company", email="none-dashboard@example.com",
                          source="test", status="New", processing_status="pending",
                          lead_score=99, priority="Hot")
        processing = Lead(organization_id=org_a, company="Processing Company", email="processing-dashboard@example.com",
                          source="test", status="New", processing_status="processing")
        other = Lead(organization_id=org_b, company="Other Tenant Hot", email="other-dashboard@example.com",
                     source="test", status="New", processing_status="failed")
        db.add_all([warm, cold, unanalyzed, processing, other])
        db.flush()
        db.add_all([
            LeadAnalysis(organization_id=org_a, lead_id=warm.id, company=warm.company,
                         email=warm.email, priority="Cold", lead_score=30, result={}, created_at=now),
            LeadAnalysis(organization_id=org_a, lead_id=warm.id, company=warm.company,
                         email=warm.email, priority="Warm", lead_score=70, result={}, created_at=now),
            LeadAnalysis(organization_id=org_a, lead_id=cold.id, company=cold.company,
                         email=cold.email, priority="Cold", lead_score=10, result={}, created_at=now),
            LeadAnalysis(organization_id=org_a, lead_id=None, company="Unlinked History",
                         email="unlinked@example.com", priority="Hot", lead_score=100, result={}, created_at=now),
            LeadAnalysis(organization_id=org_b, lead_id=other.id, company=other.company,
                         email=other.email, priority="Hot", lead_score=100, result={}, created_at=now),
        ])
        db.commit()
        warm_id = warm.id

    response = workspace["clients"]["a"].get("/api/dashboard/v2/overview", headers=_headers(org_a))
    assert response.status_code == 200
    data = response.json()
    assert data["pipeline"] == {
        "total_leads": 5, "analyzed_leads": 3, "unanalyzed_leads": 2,
        "average_current_score": 53.33,
    }
    assert data["priority_distribution"] == {"Hot": 1, "Warm": 1, "Cold": 1, "Unanalyzed": 2}
    assert data["lifecycle_distribution"] == {
        "New": 2, "Qualified": 1, "Contacted": 1,
        "Meeting": 1, "Won": 0, "Lost": 0,
    }
    assert data["processing_distribution"] == {
        "pending": 1, "processing": 1, "completed": 2, "failed": 1,
    }
    assert [(row["company"], row["lead_score"], row["priority"]) for row in data["top_opportunities"]] == [
        ("Alpha Company", 80, "Hot"), ("Warm Company", 70, "Warm"), ("Cold Company", 10, "Cold"),
    ]
    assert len({row["lead_id"] for row in data["top_opportunities"]}) == 3
    warm_events = [row for row in data["recent_analysis_activity"] if row["lead_id"] == warm_id]
    assert [row["lead_score"] for row in warm_events] == [70, 30]  # timestamp tie uses ID descending
    assert any(row["company"] == "Unlinked History" and row["lead_id"] is None for row in data["recent_analysis_activity"])
    assert "Other Tenant Hot" not in response.text

    limited = workspace["clients"]["a"].get("/api/dashboard/v2/overview", params={"limit": 1, "priority": "Warm"}, headers=_headers(org_a))
    assert limited.status_code == 200
    assert [row["lead_id"] for row in limited.json()["top_opportunities"]] == [warm_id]
    assert [row["lead_id"] for row in limited.json()["recent_analysis_activity"]] == [warm_id]
    assert limited.json()["pipeline"]["total_leads"] == 5


def test_empty_and_unanalyzed_workspace_have_null_average(tenant_workspace):
    workspace = tenant_workspace
    user_a = workspace["ids"]["users"]["a"]
    with SessionLocal() as db:
        empty = Organization(name="Dashboard Empty", slug="dashboard-empty")
        only_new = Organization(name="Dashboard New", slug="dashboard-new")
        db.add_all([empty, only_new])
        db.flush()
        db.add_all([
            OrganizationMembership(user_id=user_a, organization_id=empty.id, role="member"),
            OrganizationMembership(user_id=user_a, organization_id=only_new.id, role="member"),
            Lead(organization_id=only_new.id, company="New Only", email="new-only@example.com",
                 source="test", lead_score=0, priority="Cold"),
        ])
        db.commit()
        empty_id, new_id = empty.id, only_new.id

    client = workspace["clients"]["a"]
    empty_data = client.get("/api/dashboard/v2/overview", headers=_headers(empty_id)).json()
    assert empty_data["pipeline"] == {
        "total_leads": 0, "analyzed_leads": 0, "unanalyzed_leads": 0,
        "average_current_score": None,
    }
    assert empty_data["top_opportunities"] == empty_data["recent_analysis_activity"] == []
    new_data = client.get("/api/dashboard/v2/overview", headers=_headers(new_id)).json()
    assert new_data["pipeline"] == {
        "total_leads": 1, "analyzed_leads": 0, "unanalyzed_leads": 1,
        "average_current_score": None,
    }
    assert new_data["priority_distribution"] == {"Hot": 0, "Warm": 0, "Cold": 0, "Unanalyzed": 1}
    assert new_data["top_opportunities"] == []


def test_legacy_unlinked_priorities_remain_typed_history_without_becoming_current(tenant_workspace):
    org_a = tenant_workspace["ids"]["organizations"]["a"]
    with SessionLocal() as db:
        linked_at = db.scalar(select(LeadAnalysis.created_at).where(
            LeadAnalysis.organization_id == org_a,
            LeadAnalysis.lead_id == tenant_workspace["ids"]["leads"]["a"],
        ))
        db.add_all([
            LeadAnalysis(organization_id=org_a, lead_id=None, company="Old Unknown",
                         email="unknown-history@example.com", priority="Unknown",
                         lead_score=0, result={}, created_at=linked_at + timedelta(hours=2)),
            LeadAnalysis(organization_id=org_a, lead_id=None, company="Old High",
                         email="high-history@example.com", priority="High",
                         lead_score=75, result={}, created_at=linked_at + timedelta(hours=1)),
        ])
        db.commit()

    response = tenant_workspace["clients"]["a"].get(
        "/api/dashboard/v2/overview", headers=_headers(org_a),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["pipeline"] == {"total_leads": 1, "analyzed_leads": 1,
                                "unanalyzed_leads": 0, "average_current_score": 80.0}
    assert data["priority_distribution"] == {"Hot": 1, "Warm": 0, "Cold": 0, "Unanalyzed": 0}
    assert [row["priority"] for row in data["recent_analysis_activity"][:2]] == ["Unknown", "High"]
    assert [row["lead_id"] for row in data["recent_analysis_activity"][:2]] == [None, None]
