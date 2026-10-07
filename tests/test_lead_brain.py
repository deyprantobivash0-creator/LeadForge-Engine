"""No-network Lead Brain contract and processing integration checks."""

from datetime import timedelta
import asyncio

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from backend.ai.providers.base import ProviderMalformedOutput, ProviderTimeout, ProviderUnavailable
from backend.ai.providers.mock_provider import MockProvider
from backend.ai.providers.router import AIRouter
from backend.ai.schemas.lead_brain import StageAssessment
from backend.ai.workflow.lead_brain_workflow import LeadBrainWorkflow
from backend.database.session import SessionLocal
from backend.core.config import settings
from backend.decision.lead_scorer import LeadScorer
from backend.models import Lead, LeadAnalysis
from backend.repositories.lead_processing_repository import LeadProcessingRepository, utc_naive_now
from backend.services.lead_processing_service import LeadProcessingService
from tests.api.test_tenant_leads import headers


@pytest.mark.parametrize("score,priority", [(0,"Cold"),(59,"Cold"),(60,"Warm"),(79,"Warm"),(80,"Hot"),(100,"Hot")])
def test_priority_boundaries(score, priority):
    scorer = LeadScorer()
    assert scorer.priority_for_score(score) == priority
    assert scorer.score_components(score, score, score) == (score, priority)


def test_scoring_weights_and_component_validation():
    scorer = LeadScorer()
    assert scorer.score_components(100, 0, 0)[0] == 40
    assert scorer.score_components(0, 100, 0)[0] == 25
    assert scorer.score_components(0, 0, 100)[0] == 35
    for invalid in (-1, 101, True, "80"):
        with pytest.raises(ValueError):
            scorer.score_components(invalid, 0, 0)


def test_provider_output_is_validated_and_cannot_set_final_priority():
    class SuppliedProvider(MockProvider):
        async def generate_structured(self, prompt, schema):
            return {"score": 80, "summary": "Assessment from supplied fields.", "evidence": [{"source": "lead_data", "field": "company", "value": "A", "reasoning": "Company name was supplied."}]}

    context = {"company": "A", "email": "a@example.com", "source": "test", "industry": None}
    result = asyncio.run(LeadBrainWorkflow(SuppliedProvider()).run(context))
    assert result.final_decision.lead_score == 80
    assert result.final_decision.priority == "Hot"

    class InjectedPriority(SuppliedProvider):
        async def generate_structured(self, prompt, schema):
            return {"score": 80, "summary": "Assessment", "evidence": [{"source": "lead_data", "field": "company", "value": "A", "reasoning": "Supplied."}], "priority": "Cold"}

    with pytest.raises(ProviderMalformedOutput):
        asyncio.run(LeadBrainWorkflow(InjectedPriority()).run(context))
    class UnsupportedEvidence(SuppliedProvider):
        async def generate_structured(self, prompt, schema):
            return {"score": 80, "summary": "Unsupported", "evidence": [{"source": "lead_data", "field": "company", "value": "Other", "reasoning": "Mismatched."}]}

    with pytest.raises(ProviderMalformedOutput):
        asyncio.run(LeadBrainWorkflow(UnsupportedEvidence()).run(context))
    for bad in ({"summary": "Missing score"}, {"score": 101, "summary": "Invalid"}, {"score": "80", "summary": "Wrong type"}):
        with pytest.raises(ValidationError):
            StageAssessment.model_validate(bad)


def test_process_mock_end_to_end_and_repeat_history(tenant_workspace, monkeypatch):
    w = tenant_workspace
    provider = MockProvider()
    monkeypatch.setattr(AIRouter, "get_provider", lambda self: provider)
    client = w["clients"]["a"]
    a = w["ids"]["leads"]["a"]
    own_headers = headers(w, "a", csrf=True)
    first = client.post(f"/api/leads/{a}/process", headers=own_headers)
    assert first.status_code == 200
    assert first.json()["processing_status"] == "completed"
    assert first.json()["analysis"]["lead_score"] == 0
    assert first.json()["analysis"]["priority"] == "Cold"
    assert first.json()["analysis"]["result"]["schema_version"] == 1
    first_id = first.json()["analysis"]["id"]
    second = client.post(f"/api/leads/{a}/process", headers=own_headers)
    assert second.status_code == 200
    second_id = second.json()["analysis"]["id"]
    assert second_id != first_id
    intelligence = client.get(f"/api/leads/{a}/intelligence", headers=headers(w, "a"))
    assert intelligence.json()["analysis"]["id"] == second_id
    history = client.get(f"/api/leads/{a}/analyses", headers=headers(w, "a"))
    assert history.json()["total"] == 3
    assert [row["id"] for row in history.json()["items"][:2]] == [second_id, first_id]
    assert len(provider.calls) == 6
    with SessionLocal() as db:
        assert db.get(Lead, a).processing_status == "completed"
        assert len(list(db.scalars(select(LeadAnalysis).where(LeadAnalysis.lead_id == a)))) == 3


def test_process_tenant_auth_csrf_and_conflict(tenant_workspace, monkeypatch):
    w = tenant_workspace
    provider = MockProvider()
    monkeypatch.setattr(AIRouter, "get_provider", lambda self: provider)
    client = w["clients"]["a"]
    a, b = w["ids"]["leads"]["a"], w["ids"]["leads"]["b"]
    assert client.post(f"/api/leads/{b}/process", headers=headers(w, "a", csrf=True)).status_code == 404
    assert client.post(f"/api/leads/{b}/process", headers=headers(w, "b", csrf=True)).status_code == 403
    assert client.post(f"/api/leads/{a}/process", headers=headers(w, "a")).status_code == 403
    assert client.post(f"/api/leads/{a}/process").status_code == 400
    assert client.post(f"/api/leads/{a}/process", headers={"X-Organization-ID": str(w["ids"]["organizations"]["a"]), "X-CSRF-Token": "wrong"}).status_code == 403
    from fastapi.testclient import TestClient
    from backend.main import app
    with TestClient(app) as anonymous:
        assert anonymous.post(f"/api/leads/{a}/process", headers=headers(w, "a")).status_code == 401
    with SessionLocal() as db:
        lead = db.get(Lead, a)
        lead.processing_status = "processing"
        lead.processing_started_at = utc_naive_now()
        lead.processing_attempt_id = "active-attempt"
        db.commit()
    assert client.post(f"/api/leads/{a}/process", headers=headers(w, "a", csrf=True)).status_code == 409
    assert provider.calls == []


@pytest.mark.parametrize("mode,status", [("malformed",502),("timeout",504),("error",503)])
def test_failed_reprocessing_keeps_prior_analysis(tenant_workspace, monkeypatch, mode, status):
    w = tenant_workspace
    provider = MockProvider(mode)
    monkeypatch.setattr(AIRouter, "get_provider", lambda self: provider)
    client = w["clients"]["a"]
    a = w["ids"]["leads"]["a"]
    before = client.get(f"/api/leads/{a}/intelligence", headers=headers(w, "a")).json()["analysis"]["id"]
    response = client.post(f"/api/leads/{a}/process", headers=headers(w, "a", csrf=True))
    assert response.status_code == status
    assert client.get(f"/api/leads/{a}", headers=headers(w, "a")).json()["processing_status"] == "failed"
    assert client.get(f"/api/leads/{a}/intelligence", headers=headers(w, "a")).json()["analysis"]["id"] == before


def test_atomic_claim_and_stale_attempt_guard(tenant_workspace):
    w = tenant_workspace
    a = w["ids"]["leads"]["a"]
    oa = w["ids"]["organizations"]["a"]
    repository = LeadProcessingRepository()
    with SessionLocal() as db:
        first = repository.claim(db, oa, a)
        assert first
        db.commit()
    with SessionLocal() as db:
        assert repository.claim(db, oa, a) is None
        db.rollback()
        lead = db.get(Lead, a)
        lead.processing_started_at = utc_naive_now() - timedelta(minutes=16)
        db.commit()
    with SessionLocal() as db:
        second = repository.claim(db, oa, a)
        assert second and second != first
        db.commit()
        assert not repository.complete(db, oa, a, first, 50, "Cold", "reason", "action")
        db.rollback()
        assert repository.fail(db, oa, a, second)
        db.commit()


def test_provider_runs_without_open_transaction(tenant_workspace):
    w = tenant_workspace
    a = w["ids"]["leads"]["a"]
    oa = w["ids"]["organizations"]["a"]
    with SessionLocal() as db:
        class InspectingProvider(MockProvider):
            async def generate(self, prompt):
                assert not db.in_transaction()
                return await super().generate(prompt)

        response = asyncio.run(LeadProcessingService(db, InspectingProvider()).process(oa, a))
        assert response["processing_status"] == "completed"


def test_selected_provider_must_be_configured_no_fallback(tenant_workspace, monkeypatch):
    w = tenant_workspace
    a = w["ids"]["leads"]["a"]
    monkeypatch.setattr(settings, "AI_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    response = w["clients"]["a"].post(f"/api/leads/{a}/process", headers=headers(w, "a", csrf=True))
    assert response.status_code == 503
    assert response.json()["detail"] == "provider_not_configured"
    with SessionLocal() as db:
        assert db.get(Lead, a).processing_status == "failed"


def test_mock_provider_is_restricted_to_development_and_test(monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER", "mock")
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    from backend.ai.providers.base import ProviderNotConfigured
    with pytest.raises(ProviderNotConfigured):
        AIRouter().get_provider()


def test_gemini_adapter_uses_sdk_boundary_without_network(monkeypatch):
    from types import SimpleNamespace
    from google import genai
    from backend.ai.providers.gemini_provider import GeminiProvider

    observed = {}

    class FakeAsyncClient:
        models = None

        async def __aenter__(self):
            self.models = self
            return self

        async def __aexit__(self, *_args):
            return False

        async def generate_content(self, **kwargs):
            observed["model"] = kwargs["model"]
            observed["prompt"] = kwargs["contents"]
            observed["mime"] = kwargs["config"].response_mime_type
            return SimpleNamespace(text='{"score":0,"summary":"Insufficient data","evidence":[]}')

    class FakeClient:
        def __init__(self, *, api_key, http_options):
            observed["key_passed"] = api_key == "test-placeholder"
            observed["timeout"] = http_options.timeout
            self.aio = FakeAsyncClient()

        def close(self):
            observed["closed"] = True

    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-placeholder")
    monkeypatch.setattr(genai, "Client", FakeClient)
    # Exercise the adapter through the fake SDK; CI socket guard still forbids
    # provider network access. The environment override is restored by pytest.
    monkeypatch.delenv("LEADFORGE_CI", raising=False)
    response = asyncio.run(GeminiProvider().generate_structured("safe test prompt", StageAssessment))
    assert response.score == 0
    assert observed == {
        "key_passed": True,
        "timeout": settings.AI_TIMEOUT_SECONDS * 1000,
        "model": settings.GEMINI_MODEL,
        "prompt": "safe test prompt",
        "mime": "application/json",
        "closed": True,
    }


@pytest.mark.parametrize("failure,expected", [
    ("malformed", ProviderMalformedOutput),
    ("timeout", ProviderTimeout),
    ("unavailable", ProviderUnavailable),
])
def test_gemini_sdk_failures_are_normalized_without_network(monkeypatch, failure, expected):
    from types import SimpleNamespace
    from google import genai
    import httpx
    from backend.ai.providers.gemini_provider import GeminiProvider

    observed = {"closed": False}

    class FakeAsyncClient:
        async def __aenter__(self):
            self.models = self
            return self

        async def __aexit__(self, *_args):
            return False

        async def generate_content(self, **_kwargs):
            if failure == "timeout":
                raise httpx.ReadTimeout("simulated")
            if failure == "unavailable":
                raise RuntimeError("simulated")
            return SimpleNamespace(text='{"score":"bad","summary":"Invalid"}')

    class FakeClient:
        def __init__(self, **_kwargs):
            self.aio = FakeAsyncClient()

        def close(self):
            observed["closed"] = True

    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-placeholder")
    monkeypatch.setattr(genai, "Client", FakeClient)
    monkeypatch.delenv("LEADFORGE_CI", raising=False)
    with pytest.raises(expected):
        asyncio.run(GeminiProvider().generate_structured("safe test prompt", StageAssessment))
    assert observed["closed"]


def test_router_selects_gemini_and_deepseek_remains_unsupported(monkeypatch):
    from backend.ai.providers.gemini_provider import GeminiProvider
    from backend.ai.providers.base import ProviderNotConfigured

    monkeypatch.setattr(settings, "AI_PROVIDER", "gemini")
    assert isinstance(AIRouter().get_provider(), GeminiProvider)
    monkeypatch.setattr(settings, "AI_PROVIDER", "deepseek")
    provider = AIRouter().get_provider()
    with pytest.raises(ProviderNotConfigured):
        asyncio.run(provider.generate_structured("unused", StageAssessment))
