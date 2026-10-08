"""Direct creation restores the session and classifies only tenant/email conflicts."""
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from backend.database.session import SessionLocal
from backend.models import Lead
from backend.repositories.lead_repository import LeadRepository
from backend.services.lead_service import LeadService
from tests.api.test_tenant_leads import headers


def test_sqlite_advisory_read_race_returns_409_and_session_recovers(tenant_workspace, monkeypatch):
    monkeypatch.setattr(LeadRepository, 'get_lead_by_email', lambda *args, **kwargs: None)
    client = tenant_workspace['clients']['a']
    response = client.post('/api/leads/', headers=headers(tenant_workspace, 'a', csrf=True),
                           json={'company': 'Synthetic', 'email': 'alpha-lead@example.com', 'source': 'fixture'})
    assert response.status_code == 409
    assert client.get('/api/leads/', headers=headers(tenant_workspace, 'a')).status_code == 200


def test_sqlite_unrelated_integrity_error_is_not_duplicate(tenant_workspace):
    org_id = tenant_workspace['ids']['organizations']['a']
    with SessionLocal() as db:
        with pytest.raises(IntegrityError):
            LeadService(db).create_lead(None, 'invalid@example.com', 'fixture', org_id)
        assert db.scalar(select(Lead.id).where(Lead.organization_id == org_id, Lead.email == 'invalid@example.com')) is None
