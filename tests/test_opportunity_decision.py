"""P2-A pure policy invariants and real authenticated read-only API behavior."""

from datetime import datetime
from itertools import product
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from sqlalchemy import event, select

from backend.decision.lead_scorer import LeadScorer
from backend.decision.opportunity_policy import evaluate, extract_features
from backend.schemas.opportunity_decision import OpportunityDecision


def lead_case(company=95, contact=95, intent=95, **changes):
    """Synthetic existing-field data, not a provider invocation or invented ICP."""
    lead = SimpleNamespace(id=1, organization_id=1, company="Synthetic Company",
        email="synthetic@example.invalid", source="fixture", industry="Software",
        status="Meeting", processing_status="completed", lead_score=17, priority="Cold")
    lead.__dict__.update(changes)
    score, priority = LeadScorer().score_components(company, contact, intent)
    result = {"schema_version": 1, "final_decision": {"lead_score": score,
        "priority": priority.value, "recommended_action": "Synthetic existing assessment"}}
    for name, value, field in (("company", company, "company"), ("contact", contact, "email"), ("intent", intent, "industry")):
        result[name] = {"score": value, "summary": "Stored estimate, not externally verified.",
            "evidence": [{"source": "lead_data", "field": field, "value": getattr(lead, field) or "absent",
                          "reasoning": "Synthetic stored assessment."}]}
    analysis = SimpleNamespace(organization_id=lead.organization_id, lead_id=lead.id,
        company=lead.company, email=lead.email, lead_score=score, priority=priority.value, result=result)
    return lead, analysis


def decide(*args, **kwargs):
    return evaluate(extract_features(*lead_case(*args, **kwargs)))


def semantics(decision):
    return decision.model_dump(mode="json", exclude={"generated_at"})


def test_strong_lead_is_explainable_and_not_generically_review_required():
    result = decide()
    assert (result.fit_score, result.readiness_score, result.opportunity_score) == (95, 94, 95)
    assert result.confidence == .88
    assert result.recommended_action == "PREPARE_OUTREACH"
    assert not result.human_review_required and not result.risk_flags and not result.missing_signals
    assert result.opportunity_score != 17  # Historical Lead score is not redefined.
    assert result.decision_version == "revenue_brain_v1"
    assert "not verified ICP" in result.reasons[0]
    assert "no observed engagement" in result.reasons[1]


def test_strong_fit_low_readiness_has_a_timing_appropriate_recommendation():
    result = decide(intent=10, status="New")
    assert result.fit_score == 95 and result.readiness_score == 7
    assert 35 < result.opportunity_score < 70
    assert result.recommended_action == "QUALIFY"
    assert not result.human_review_required


def test_low_fit_remains_low_despite_positive_other_signals():
    result = decide(company=10)
    assert result.fit_score == 10 and result.opportunity_score < decide().opportunity_score
    assert result.recommended_action == "DEPRIORITIZE"
    assert "LOW_ASSESSED_FIT" in result.risk_flags
    assert any("estimate is low" in r for r in result.reasons)


def test_sparse_unknown_is_not_zero_or_fabricated_role_need_or_intent():
    lead, _ = lead_case()
    lead.company, lead.email, lead.industry = "", "", None
    result = evaluate(extract_features(lead, None))
    assert result.opportunity_score > 0 and result.confidence < .65
    assert len(result.missing_signals) == 5 and result.human_review_required
    assert result.recommended_action == "RESEARCH_MORE"
    assert all(e.observed_value in {"missing", "unknown", "unavailable", "Meeting"} or e.source == "policy" for e in result.evidence)


def test_conflict_reduces_confidence_and_requires_reconciliation():
    result = decide(intent=0)
    assert "CONFLICTING_SIGNALS" in result.risk_flags
    assert result.confidence < decide().confidence
    assert result.human_review_required and result.recommended_action == "HUMAN_REVIEW"
    assert any("conflicts" in r for r in result.reasons)


@pytest.mark.parametrize("company,contact,intent", list(product((0, 1, 99, 100), repeat=3)))
def test_extreme_assessments_are_bounded_deterministic_and_evidence_consistent(company, contact, intent):
    first, second = decide(company, contact, intent), decide(company, contact, intent)
    assert semantics(first) == semantics(second)
    assert all(0 <= value <= 100 for value in (first.fit_score, first.readiness_score, first.opportunity_score))
    assert 0 <= first.confidence <= 1
    assert first.fit_score == company
    evidence = {e.signal: e for e in first.evidence}
    for name, score in (("company", company), ("contact", contact), ("intent", intent)):
        assert evidence[name + "_assessment"].observed_value == str(score)
    assert "Synthetic Company" not in first.model_dump_json()
    assert "synthetic@example.invalid" not in first.model_dump_json()


@pytest.mark.parametrize("status", ["New", "Qualified", "Contacted", "Meeting", "Won", "Lost", "legacy", None, ""])
def test_lifecycle_is_explicit_and_closed_leads_are_not_outreach_targets(status):
    result = decide(status=status)
    if status in {"Won", "Lost"}:
        assert result.opportunity_score == 0 and result.recommended_action == "DEPRIORITIZE"
    elif status in {None, "", "legacy"}:
        assert "UNKNOWN_LIFECYCLE" in result.risk_flags
        assert "lifecycle_state" in result.missing_signals and result.human_review_required
    else:
        assert "UNKNOWN_LIFECYCLE" not in result.risk_flags


@pytest.mark.parametrize("corruption", ["legacy", "nan", "negative", "excess", "wrong_type", "extra", "score_mismatch", "priority_mismatch", "foreign", "unlinked", "stale", "evidence_changed", "absent_field", "no_evidence", "derived"])
def test_untrustworthy_or_weak_legacy_assessments_reduce_confidence(corruption):
    lead, analysis = lead_case()
    if corruption == "legacy": analysis.result = {"arbitrary": "secret-token-not-for-response"}
    elif corruption in {"nan", "negative", "excess", "wrong_type"}:
        analysis.result["company"]["score"] = {"nan": float("nan"), "negative": -1, "excess": 101, "wrong_type": "95"}[corruption]
    elif corruption == "extra": analysis.result["secret_token"] = "never-return"
    elif corruption == "score_mismatch": analysis.lead_score = 3
    elif corruption == "priority_mismatch": analysis.result["final_decision"]["priority"] = "Cold"
    elif corruption == "foreign": analysis.organization_id = 2
    elif corruption == "unlinked": analysis.lead_id = None
    elif corruption == "stale": lead.company = "Changed Company"
    elif corruption == "evidence_changed": lead.industry = "Changed industry"
    elif corruption == "absent_field": lead.industry = None
    elif corruption == "no_evidence":
        for stage in ("company", "contact", "intent"): analysis.result[stage]["evidence"] = []
    elif corruption == "derived":
        for stage in ("company", "contact", "intent"): analysis.result[stage]["evidence"][0]["source"] = "derived"
    result = evaluate(extract_features(lead, analysis))
    assert result.human_review_required and result.confidence < decide().confidence
    assert result.recommended_action in {"HUMAN_REVIEW", "RESEARCH_MORE"}
    assert "secret-token" not in result.model_dump_json() and "never-return" not in result.model_dump_json()


def test_confidence_is_coverage_and_provenance_not_magnitude():
    assert decide(0, 0, 0, status="New").confidence == decide(100, 100, 100, status="New").confidence
    assert decide(processing_status="processing").human_review_required


@pytest.mark.parametrize("scores,action", [
    ((95, 95, 53), "QUALIFY"), ((95, 95, 54), "PREPARE_OUTREACH"),
    ((62, 62, 62), "NURTURE"), ((63, 63, 63), "PREPARE_OUTREACH"),
    ((29, 95, 95), "DEPRIORITIZE"), ((30, 95, 95), "NURTURE"),
])
def test_recommendation_threshold_edges(scores, action):
    assert decide(*scores).recommended_action == action


@pytest.mark.parametrize("field,value", [
    ("opportunity_score", -1), ("fit_score", 101), ("readiness_score", float("nan")),
    ("opportunity_score", True), ("confidence", float("inf")), ("confidence", float("nan")),
    ("confidence", -0.1), ("confidence", 1.1), ("recommended_action", "SEND_EMAIL"),
    ("decision_version", "unversioned"), ("reasons", ["x"] * 13),
    ("evidence", [{}] * 13), ("missing_signals", ["role"]), ("generated_at", datetime(2026, 1, 1)),
])
def test_response_contract_rejects_invalid_values(field, value):
    payload = decide().model_dump()
    payload[field] = value
    with pytest.raises(ValidationError):
        OpportunityDecision.model_validate(payload)


def seed_decision(db, lead):
    from backend.models import LeadAnalysis
    _, analysis = lead_case()
    lead.company, lead.email, lead.industry = analysis.company, analysis.email, "Software"
    lead.status, lead.processing_status = "Meeting", "completed"
    db.add(LeadAnalysis(organization_id=lead.organization_id, lead_id=lead.id,
        company=lead.company, email=lead.email, lead_score=analysis.lead_score,
        priority=analysis.priority, result=analysis.result))
    db.flush()


def snapshot(engine):
    from backend.database.base import Base
    # Test-only whole disposable fixture snapshot, including audit/auth tables.
    with engine.connect() as connection:
        return {table.name: sorted(repr(tuple(row)) for row in connection.execute(select(table)))
                for table in Base.metadata.sorted_tables}


def test_api_typed_tenant_private_read_only_and_offline(tenant_workspace, monkeypatch):
    from backend.ai.providers.router import AIRouter
    from backend.database.session import SessionLocal, engine
    from backend.models import Lead
    w = tenant_workspace
    own, foreign = w["ids"]["leads"]["a"], w["ids"]["leads"]["b"]
    headers = {"X-Organization-ID": str(w["ids"]["organizations"]["a"])}
    with SessionLocal() as db:
        seed_decision(db, db.get(Lead, own))
        db.commit()
    def forbidden(*args, **kwargs): raise AssertionError("Decisioning invoked a provider")
    monkeypatch.setattr(AIRouter, "get_provider", forbidden)
    before = snapshot(engine)
    client = w["clients"]["a"]
    response = client.get(f"/api/leads/{own}/opportunity-decision", headers=headers)
    assert response.status_code == 200
    result = OpportunityDecision.model_validate(response.json())
    assert result.recommended_action == "PREPARE_OUTREACH"
    assert "no-store" in response.headers["cache-control"]
    assert snapshot(engine) == before
    foreign_response = client.get(f"/api/leads/{foreign}/opportunity-decision", headers=headers)
    missing_response = client.get("/api/leads/9223372036854775807/opportunity-decision", headers=headers)
    assert foreign_response.status_code == missing_response.status_code == 404
    assert foreign_response.json() == missing_response.json()
    assert client.get(f"/api/leads/{own}/opportunity-decision").status_code == 400
    assert client.get(f"/api/leads/{own}/opportunity-decision", headers={"X-Organization-ID": str(w["ids"]["organizations"]["b"])}).status_code == 403
    for value in ("0", "-1", "invalid", "9223372036854775808"):
        assert client.get(f"/api/leads/{value}/opportunity-decision", headers=headers).status_code == 422
    from fastapi.testclient import TestClient
    from backend.main import app
    with TestClient(app) as anonymous:
        assert anonymous.get(f"/api/leads/{own}/opportunity-decision", headers=headers).status_code == 401
    assert snapshot(engine) == before


def test_service_two_scoped_reads_no_flush_or_settlement(tenant_workspace):
    from backend.database.session import SessionLocal, engine
    from backend.models import Lead
    from backend.services.opportunity_decision_service import OpportunityDecisionService
    w = tenant_workspace
    with SessionLocal() as db:
        lead = db.get(Lead, w["ids"]["leads"]["a"])
        lead.notes = "Pending unrelated caller work must not flush"
        statements = []
        def collect(_c, _cursor, statement, *_args): statements.append(statement)
        def prohibited(*_args): raise AssertionError("Decisioning flushed or settled")
        event.listen(engine, "before_cursor_execute", collect)
        for name in ("before_flush", "before_commit", "after_rollback"):
            event.listen(db, name, prohibited)
        try:
            result = OpportunityDecisionService(db).get_decision(lead.id, lead.organization_id)
            assert result.lead_id == lead.id
            assert len(statements) == 2 and all(s.lstrip().upper().startswith("SELECT") for s in statements)
            assert lead in db.dirty
            assert db.in_transaction()
            with pytest.raises(ValueError): OpportunityDecisionService(db).get_decision(lead.id, None)
        finally:
            event.remove(engine, "before_cursor_execute", collect)
            for name in ("before_flush", "before_commit", "after_rollback"):
                event.remove(db, name, prohibited)


def test_new_modules_have_no_unauthorized_transaction_ownership():
    from pathlib import Path
    from tests.test_transaction_architecture import violations
    for name in ("backend/decision/opportunity_policy.py", "backend/services/opportunity_decision_service.py", "backend/schemas/opportunity_decision.py"):
        assert violations(Path(name).read_text(encoding="utf-8"), name) == []


def assert_truthful_provenance(decision):
    """Missing factors must not masquerade as stored evidence in either channel."""
    evidence = {entry.signal: entry for entry in decision.evidence}
    for signal in ("company_assessment", "contact_assessment", "intent_assessment", "qualification"):
        entry = evidence[signal]
        if entry.observed_value == "unavailable":
            assert entry.source == "policy"
            assert "unavailable" in entry.effect.lower() and "prior" in entry.effect.lower()
            assert "stored estimate" not in entry.effect.lower()
            if signal != "qualification":
                assert signal in decision.missing_signals
        else:
            assert entry.source == "stored_assessment"
            assert signal not in decision.missing_signals
    fit_reason, intent_reason, qualification_reason = decision.reasons[:3]
    for signal, reason in (("company_assessment", fit_reason), ("intent_assessment", intent_reason),
                           ("qualification", qualification_reason)):
        if evidence[signal].observed_value == "unavailable":
            assert "unavailable" in reason.lower() and "prior" in reason.lower()
            assert "stored" not in reason.lower() and "existing" not in reason.lower()
        else:
            assert "stored" in reason.lower() and "unavailable" not in reason.lower()
    assert "no observed engagement" in intent_reason
    if any(e.observed_value == "unavailable" for e in evidence.values()):
        assert "INSUFFICIENT_DATA" in decision.risk_flags and decision.human_review_required


def test_r1_exact_no_analysis_blocker_uses_explicit_policy_priors():
    lead, _ = lead_case()
    first, second = (evaluate(extract_features(lead, None)) for _ in range(2))
    assert_truthful_provenance(first)
    assert semantics(first) == semantics(second)
    assert (first.opportunity_score, first.fit_score, first.readiness_score, first.confidence) == (45, 40, 55, .4)
    assert first.recommended_action == "RESEARCH_MORE" and first.human_review_required
    text = " ".join(first.reasons).lower()
    assert "stored intent assessment" not in text and "existing qualification" not in text
    assert set(first.missing_signals) == {"company_assessment", "contact_assessment", "intent_assessment"}


@pytest.mark.parametrize("available", list(product((False, True), repeat=3)))
def test_r1_each_partial_analysis_combination_has_factor_specific_provenance(available):
    lead, analysis = lead_case()
    for name, exists in zip(("company", "contact", "intent"), available):
        if not exists:
            analysis.result[name]["evidence"] = []
    decision = evaluate(extract_features(lead, analysis))
    assert_truthful_provenance(decision)
    evidence = {entry.signal: entry for entry in decision.evidence}
    for name, exists in zip(("company", "contact", "intent"), available):
        entry = evidence[name + "_assessment"]
        assert entry.observed_value == ("95" if exists else "unavailable")
        if exists:
            assert "Stored estimate" in entry.effect
    assert (evidence["qualification"].source == "stored_assessment") == all(available)


@pytest.mark.parametrize("state", ["invalid", "stale", "empty_evidence", "missing_industry"])
def test_r1_rejected_or_unsupported_analysis_cannot_claim_observations(state):
    lead, analysis = lead_case()
    if state == "invalid":
        analysis.result = {"legacy": "not an assessment"}
    elif state == "stale":
        analysis.company = "Old Company"
    elif state == "empty_evidence":
        for stage in ("company", "contact", "intent"):
            analysis.result[stage]["evidence"] = []
    else:
        lead.industry = None
    assert_truthful_provenance(evaluate(extract_features(lead, analysis)))


def test_r1_unknown_lifecycle_prior_is_not_labeled_as_a_lead_observation():
    decision = decide(status="legacy")
    lifecycle = next(e for e in decision.evidence if e.signal == "lifecycle")
    assert lifecycle.source == "policy" and lifecycle.observed_value == "unknown"
    assert "unavailable" in lifecycle.effect and "neutral" in lifecycle.effect
    assert any("Lifecycle state is unavailable" in r for r in decision.reasons)
    assert "lifecycle_state" in decision.missing_signals


def test_r1_supported_zero_estimates_are_not_mislabeled_as_missing():
    decision = decide(0, 0, 0, status="New")
    assert_truthful_provenance(decision)
    assert not decision.missing_signals
    assert all("unavailable" not in r for r in decision.reasons)


@pytest.mark.parametrize("scores,status,expected", [
    ((96, 92, 94), "Meeting", (95, 96, 93, .88, "PREPARE_OUTREACH", False)),
    ((96, 92, 10), "New", (59, 96, 7, .88, "QUALIFY", False)),
    ((12, 92, 94), "Meeting", (59, 12, 93, .88, "DEPRIORITIZE", False)),
    ((60, 60, 60), "Meeting", (67, 60, 69, .88, "NURTURE", False)),
    ((96, 92, 0), "Meeting", (65, 96, 27, .63, "HUMAN_REVIEW", True)),
])
def test_r1_known_pre_repair_scores_and_recommendations_are_unchanged(scores, status, expected):
    d = decide(*scores, status=status)
    assert (d.opportunity_score, d.fit_score, d.readiness_score, d.confidence,
            d.recommended_action, d.human_review_required) == expected


@pytest.mark.parametrize("scenario", ["no_analysis", "full", "partial", "sparse", "conflict"])
def test_r1_authenticated_api_consistency_matrix_is_read_only_and_tenant_safe(tenant_workspace, monkeypatch, scenario):
    from copy import deepcopy
    from sqlalchemy import delete
    from backend.ai.providers.router import AIRouter
    from backend.database.session import SessionLocal, engine
    from backend.models import Lead, LeadAnalysis
    from backend.repositories.lead_analysis_repository import LeadAnalysisRepository
    w = tenant_workspace
    own, foreign = w["ids"]["leads"]["a"], w["ids"]["leads"]["b"]
    organization = w["ids"]["organizations"]["a"]
    with SessionLocal() as db:
        lead = db.get(Lead, own)
        db.execute(delete(LeadAnalysis).where(LeadAnalysis.organization_id == organization, LeadAnalysis.lead_id == own))
        if scenario in {"no_analysis", "sparse"}:
            lead.status = "Meeting"
            if scenario == "sparse":
                lead.company, lead.email, lead.industry = "", "", None
        else:
            seed_decision(db, lead)
            analysis = LeadAnalysisRepository().get_current_for_lead(db, own, organization)
            result = deepcopy(analysis.result)
            if scenario == "partial":
                result["intent"]["evidence"] = []
            elif scenario == "conflict":
                _, conflicting = lead_case(intent=0)
                result = conflicting.result
                analysis.lead_score, analysis.priority = conflicting.lead_score, conflicting.priority
            analysis.result = result
        db.commit()
    def prohibited(*_args, **_kwargs):
        raise AssertionError("Truthfulness repair attempted provider access")
    monkeypatch.setattr(AIRouter, "get_provider", prohibited)
    before = snapshot(engine)
    headers = {"X-Organization-ID": str(organization)}
    client = w["clients"]["a"]
    responses = [client.get(f"/api/leads/{own}/opportunity-decision", headers=headers) for _ in range(2)]
    assert all(r.status_code == 200 for r in responses)
    first, second = (OpportunityDecision.model_validate(r.json()) for r in responses)
    assert_truthful_provenance(first)
    assert semantics(first) == semantics(second)
    if scenario == "no_analysis":
        assert first.recommended_action == "RESEARCH_MORE"
    elif scenario == "full":
        assert not first.missing_signals and not first.human_review_required
    elif scenario == "partial":
        assert first.missing_signals == ["intent_assessment"]
    elif scenario == "sparse":
        assert {"company_profile", "contact_details"} <= set(first.missing_signals)
    else:
        assert "CONFLICTING_SIGNALS" in first.risk_flags
    foreign_response = client.get(f"/api/leads/{foreign}/opportunity-decision", headers=headers)
    missing_response = client.get("/api/leads/999999999/opportunity-decision", headers=headers)
    assert foreign_response.status_code == missing_response.status_code == 404
    assert foreign_response.json() == missing_response.json()
    assert snapshot(engine) == before
