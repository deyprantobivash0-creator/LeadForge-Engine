from datetime import timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from backend.database.session import SessionLocal
from backend.models import Lead, LeadAnalysis
from backend.repositories.lead_analysis_repository import LeadAnalysisRepository
from backend.services.analysis_service import AnalysisService
from tests.api.test_tenant_leads import headers


def test_history_current_and_api_are_tenant_owned(tenant_workspace):
    w = tenant_workspace
    a, b = w["ids"]["leads"]["a"], w["ids"]["leads"]["b"]
    oa, ob = w["ids"]["organizations"]["a"], w["ids"]["organizations"]["b"]
    with SessionLocal() as db:
        old = LeadAnalysisRepository().get_current_for_lead(db, a, oa)
        db.add_all([
            LeadAnalysis(organization_id=oa, lead_id=a, company="Alpha Company", email="alpha-lead@example.com", priority="Warm", lead_score=70, result={"version": 2}, created_at=old.created_at + timedelta(seconds=1)),
            LeadAnalysis(organization_id=ob, lead_id=b, company="Beta Company", email="beta-lead@example.com", priority="Cold", lead_score=30, result={"version": 2}, created_at=old.created_at + timedelta(seconds=1)),
        ])
        db.commit()
        current = LeadAnalysisRepository().get_current_for_lead(db, a, oa)
        assert current.result == {"version": 2}
        history, total = LeadAnalysisRepository().get_history_for_lead(db, a, oa)
        assert total == 2 and [row.id for row in history] == [current.id, old.id]
        assert LeadAnalysisRepository().get_current_for_lead(db, b, oa) is None
    client = w["clients"]["a"]
    assert client.get(f"/api/leads/{a}", headers=headers(w, "a")).json()["current_analysis"]["id"] == current.id
    assert client.get(f"/api/leads/{a}/intelligence", headers=headers(w, "a")).json()["analysis"]["id"] == current.id
    response = client.get(f"/api/leads/{a}/analyses?limit=1", headers=headers(w, "a"))
    assert response.status_code == 200 and response.json()["total"] == 2
    assert [item["id"] for item in response.json()["items"]] == [current.id]
    assert client.get(f"/api/leads/{b}/analyses", headers=headers(w, "a")).status_code == 404
    assert client.get(f"/api/leads/{a}/analyses", headers=headers(w, "b")).status_code == 403


def test_cross_tenant_database_link_rejected_and_failed_write_preserves_current(tenant_workspace):
    w = tenant_workspace
    oa = w["ids"]["organizations"]["a"]
    a, b = w["ids"]["leads"]["a"], w["ids"]["leads"]["b"]
    with SessionLocal() as db:
        prior = LeadAnalysisRepository().get_current_for_lead(db, a, oa).id
        db.add(LeadAnalysis(organization_id=oa, lead_id=b, company="Wrong", email="wrong@example.com", priority="Hot", lead_score=90, result={}))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        with pytest.raises(ValueError):
            AnalysisService(db).save_analysis(organization_id=oa, lead_id=a, company="Alpha", email="alpha-lead@example.com", result={"final_decision": {"priority": "High", "lead_score": 90}})
        assert LeadAnalysisRepository().get_current_for_lead(db, a, oa).id == prior


def test_lifecycle_values_and_empty_detail(tenant_workspace):
    w = tenant_workspace
    client = w["clients"]["a"]
    a = w["ids"]["leads"]["a"]
    for status in ["New", "Qualified", "Contacted", "Meeting", "Won", "Lost"]:
        response = client.patch(f"/api/leads/{a}/lifecycle", json={"status": status}, headers=headers(w, "a", csrf=True))
        assert response.status_code == 200 and response.json()["status"] == status
    for status in ["In Progress", "Converted"]:
        assert client.patch(f"/api/leads/{a}/lifecycle", json={"status": status}, headers=headers(w, "a", csrf=True)).status_code == 422
    created = client.post("/api/leads/", json={"company": "Empty", "email": "empty@example.com", "source": "test"}, headers=headers(w, "a", csrf=True))
    assert created.status_code == 200
    detail = client.get(f"/api/leads/{created.json()['id']}", headers=headers(w, "a"))
    assert detail.json()["current_analysis"] is None


def test_repeated_validated_persistence_creates_history_and_tie_breaks(tenant_workspace):
    w = tenant_workspace
    a = w["ids"]["leads"]["a"]
    oa = w["ids"]["organizations"]["a"]
    with SessionLocal() as db:
        first = LeadAnalysisRepository().get_current_for_lead(db, a, oa)
        moment = first.created_at + timedelta(seconds=10)
        saved_ids = []
        for score in (60, 90):
            row = AnalysisService(db).save_analysis(
                organization_id=oa, lead_id=a, company="Alpha Company",
                email="alpha-lead@example.com",
                result={"final_decision": {"priority": "Warm" if score == 60 else "Hot", "lead_score": score}},
            )
            row.created_at = moment
            db.flush()
            saved_ids.append(row.id)
        db.commit()
        history, total = LeadAnalysisRepository().get_history_for_lead(db, a, oa)
        assert total == 3
        assert [row.id for row in history] == [saved_ids[1], saved_ids[0], first.id]


def test_failed_status_retains_prior_intelligence(tenant_workspace):
    w = tenant_workspace
    a = w["ids"]["leads"]["a"]
    oa = w["ids"]["organizations"]["a"]
    with SessionLocal() as db:
        prior_id = LeadAnalysisRepository().get_current_for_lead(db, a, oa).id
        db.get(Lead, a).processing_status = "failed"
        db.commit()
    detail = w["clients"]["a"].get(f"/api/leads/{a}", headers=headers(w, "a"))
    assert detail.status_code == 200
    assert detail.json()["processing_status"] == "failed"
    assert detail.json()["current_analysis"]["id"] == prior_id
