import csv
import io
from datetime import date, datetime, timedelta

from fastapi.testclient import TestClient

from backend.database.session import SessionLocal
from backend.main import app
from backend.models import LeadAnalysis
from backend.services.report_v2_service import ReportV2Service


def headers(workspace, tenant):
    return {"X-Organization-ID": str(workspace["ids"]["organizations"][tenant])}


def test_period_validation():
    assert ReportV2Service.window("custom", date(2026, 1, 1), date(2026, 1, 1)) == (
        datetime(2026, 1, 1), datetime(2026, 1, 2))
    for start, end in [(None, None), (date(2026, 1, 2), date(2026, 1, 1)),
                       (date(2025, 1, 1), date(2026, 1, 1))]:
        try:
            ReportV2Service.window("custom", start, end)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid custom range accepted")


def test_report_history_unique_rank_and_export(tenant_workspace):
    w = tenant_workspace
    a, b = w["ids"]["organizations"]["a"], w["ids"]["organizations"]["b"]
    lead_a = w["ids"]["leads"]["a"]
    now = datetime.utcnow()
    with SessionLocal() as db:
        db.add_all([
            LeadAnalysis(organization_id=a, lead_id=lead_a, company="Alpha Company", email="alpha-lead@example.com", priority="Warm", lead_score=60, result={}, created_at=now - timedelta(hours=1)),
            LeadAnalysis(organization_id=a, company='=SUM(1,2), "Legacy"', email="legacy@example.com", priority="High", lead_score=40, result={}, created_at=now - timedelta(hours=2)),
            LeadAnalysis(organization_id=b, company="Alpha Company", email="alpha-lead@example.com", priority="Hot", lead_score=100, result={}, created_at=now - timedelta(hours=1)),
        ])
        db.commit()
    client = w["clients"]["a"]
    response = client.get("/api/reports/v2/overview", headers=headers(w, "a"))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["summary"] == {
        "analysis_events": 3, "unique_analyzed_leads": 1, "average_analysis_score": 60.0,
        "hot_events": 1, "warm_events": 1, "cold_events": 0, "other_priority_events": 1,
    }
    assert sum(point["analysis_events"] for point in body["activity"]) == 3
    assert len(body["top_opportunities"]) == 1
    assert body["top_opportunities"][0]["score"] == 80
    assert [item["lead_id"] for item in body["recent_analysis_events"]].count(lead_a) == 2
    assert any(item["lead_id"] is None for item in body["recent_analysis_events"])
    assert "100" not in [str(item["score"]) for item in body["recent_analysis_events"]]
    exported = client.get("/api/reports/v2/export.csv", headers=headers(w, "a"))
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("text/csv")
    rows = list(csv.DictReader(io.StringIO(exported.text)))
    assert len(rows) == 3
    assert any(row["company"] == "'=SUM(1,2), \"Legacy\"" for row in rows)
    assert all(row["score"] != "100" for row in rows)


def test_report_auth_ranges_empty_and_tenant(tenant_workspace):
    w = tenant_workspace
    client = w["clients"]["a"]
    with TestClient(app, base_url="https://testserver") as anonymous:
        assert anonymous.get("/api/reports/v2/overview", headers=headers(w, "a")).status_code == 401
        assert anonymous.get("/api/reports/v2/export.csv", headers=headers(w, "a")).status_code == 401
    assert client.get("/api/reports/v2/overview").status_code == 400
    assert client.get("/api/reports/v2/overview", headers=headers(w, "b")).status_code == 403
    assert client.get("/api/reports/v2/export.csv", headers=headers(w, "b")).status_code == 403
    assert client.get("/api/reports/v2/overview", params={"preset": "custom"}, headers=headers(w, "a")).status_code == 422
    assert client.get("/api/reports/v2/overview", params={"preset": "custom", "start": "2026-01-02", "end": "2026-01-01"}, headers=headers(w, "a")).status_code == 422
    empty = client.get("/api/reports/v2/overview", params={"preset": "custom", "start": "2020-01-01", "end": "2020-01-02"}, headers=headers(w, "a"))
    assert empty.status_code == 200
    assert empty.json()["summary"]["analysis_events"] == 0
    assert empty.json()["summary"]["average_analysis_score"] is None
    assert empty.json()["top_opportunities"] == []
    assert empty.json()["recent_analysis_events"] == []
    assert w["clients"]["b"].get("/api/reports/v2/overview", headers=headers(w, "b")).json()["summary"]["analysis_events"] == 1
