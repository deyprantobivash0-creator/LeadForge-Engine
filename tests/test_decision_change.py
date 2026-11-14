"""P2-C canonical comparison invariants and authenticated read composition."""

from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session

from backend.decision.decision_change import compare_decisions
from backend.schemas.decision_change import DecisionChangeResponse
from backend.schemas.decision_ledger import DecisionLedgerRecord
from backend.schemas.opportunity_decision import DecisionEvidence, DecisionRisk, MissingSignal
from tests.test_opportunity_decision import decide, snapshot


def pair(before=None, after=None):
    current = decide(50, 50, 50, status="Contacted")
    previous = DecisionLedgerRecord.capture(current, current.generated_at + timedelta(seconds=1))
    return previous.model_copy(update=before or {}), current.model_copy(update=after or {})


def test_unchanged_ignores_identity_times_and_collection_order():
    previous, current = pair()
    previous = previous.model_copy(update={"id": uuid4(), "decision_generated_at": previous.decision_generated_at - timedelta(days=1),
        "evidence": list(reversed(previous.evidence)), "reasons": list(reversed(previous.reasons))})
    result = compare_decisions(previous, current)
    assert result.overall_direction == "UNCHANGED" and not result.material_change
    assert (result.opportunity_score_delta, result.fit_score_delta, result.readiness_score_delta, result.confidence_delta) == (0, 0, 0, 0)
    assert not result.recommendation_changed and not result.human_review_changed
    assert not result.added_risk_flags and not result.removed_risk_flags
    assert not result.added_missing_signals and not result.resolved_missing_signals
    assert result.to_kind == "current_computed" and result.from_decision_id == previous.id
    assert compare_decisions(previous, current).model_dump_json() == result.model_dump_json()


@pytest.mark.parametrize("delta,direction", [(10, "IMPROVED"), (-10, "DECLINED")])
def test_scores_move_together(delta, direction):
    previous, current = pair()
    current = current.model_copy(update={"opportunity_score": previous.opportunity_score + delta,
        "fit_score": previous.fit_score + delta, "readiness_score": previous.readiness_score + delta})
    result = compare_decisions(previous, current)
    assert result.overall_direction == direction and result.material_change
    assert result.opportunity_score_delta == result.fit_score_delta == result.readiness_score_delta == delta


def test_mixed_never_hides_decreased_confidence_or_new_risk():
    previous, current = pair(after={"opportunity_score": 80, "confidence": .63, "risk_flags": [DecisionRisk.LOW_CONFIDENCE]})
    result = compare_decisions(previous, current)
    assert result.overall_direction == "MIXED" and result.material_change
    assert result.confidence_delta == -.25 and result.added_risk_flags == [DecisionRisk.LOW_CONFIDENCE]


@pytest.mark.parametrize("field,below,boundary", [("opportunity_score", 4, 5), ("fit_score", 9, 10), ("readiness_score", 9, 10), ("confidence", .04, .05)])
@pytest.mark.parametrize("sign", [-1, 1])
def test_central_material_thresholds_both_directions(field, below, boundary, sign):
    from decimal import Decimal
    previous, current = pair()
    def change(amount):
        value = Decimal(str(getattr(previous, field))) + Decimal(str(sign * amount))
        return current.model_copy(update={field: float(value) if field == "confidence" else int(value)})
    assert not compare_decisions(previous, change(below)).material_change
    assert compare_decisions(previous, change(boundary)).material_change


def test_recommendation_only_is_explicit_unranked_and_material():
    from backend.schemas.opportunity_decision import RecommendedAction
    previous, current = pair(after={"recommended_action": RecommendedAction.PREPARE_OUTREACH})
    result = compare_decisions(previous, current)
    assert result.recommendation_changed and result.material_change and result.overall_direction == "MIXED"
    assert result.previous_recommendation == previous.recommended_action
    assert result.current_recommendation == "PREPARE_OUTREACH" and result.opportunity_score_delta == 0
    assert "No action is implied" in " ".join(result.explanations)


@pytest.mark.parametrize("before,after,direction", [(False, True, "DECLINED"), (True, False, "IMPROVED"), (True, True, "UNCHANGED"), (False, False, "UNCHANGED")])
def test_review_transitions(before, after, direction):
    previous, current = pair({"human_review_required": before}, {"human_review_required": after})
    result = compare_decisions(previous, current)
    assert result.human_review_changed == (before != after)
    assert result.previous_human_review_required is before and result.current_human_review_required is after
    assert result.overall_direction == direction and result.material_change == (before != after)


@pytest.mark.parametrize("field,values", [("risk_flags", [DecisionRisk.LOW_CONFIDENCE, DecisionRisk.STALE_ANALYSIS]),
    ("missing_signals", [MissingSignal.COMPANY_ASSESSMENT, MissingSignal.INTENT_ASSESSMENT])])
def test_set_order_and_duplicates_are_semantically_irrelevant(field, values):
    previous, current = pair({field: values}, {field: [*reversed(values), values[0]]})
    result = compare_decisions(previous, current)
    assert result.overall_direction == "UNCHANGED" and not result.material_change


def test_added_removed_risks_and_newly_missing_resolved_signals():
    previous, current = pair({"risk_flags": [DecisionRisk.STALE_ANALYSIS], "missing_signals": [MissingSignal.COMPANY_ASSESSMENT]},
        {"risk_flags": [DecisionRisk.LOW_CONFIDENCE], "missing_signals": [MissingSignal.INTENT_ASSESSMENT]})
    result = compare_decisions(previous, current)
    assert result.added_risk_flags == [DecisionRisk.LOW_CONFIDENCE] and result.removed_risk_flags == [DecisionRisk.STALE_ANALYSIS]
    assert result.added_missing_signals == [MissingSignal.INTENT_ASSESSMENT] and result.resolved_missing_signals == [MissingSignal.COMPANY_ASSESSMENT]
    assert result.overall_direction == "MIXED" and result.material_change


def test_evidence_uses_structured_identity_and_safe_normalization():
    a = DecisionEvidence(signal="intent_assessment", source="policy", observed_value="Neutral 40", effect="No estimate available.")
    b = a.model_copy(update={"effect": "No   estimate available.\n"})
    previous, current = pair({"evidence": [a]}, {"evidence": [b]})
    assert not compare_decisions(previous, current).evidence_changed
    current = current.model_copy(update={"evidence": [a.model_copy(update={"source": "stored_assessment"})]})
    result = compare_decisions(previous, current)
    assert result.evidence_changed and result.evidence_provenance_changed
    assert result.added_evidence[0].source == "stored_assessment" and result.removed_evidence[0].source == "policy"
    assert result.overall_direction == "MIXED" and result.material_change


def test_evidence_different_values_for_one_signal_are_not_overwritten():
    a = DecisionEvidence(signal="fixture", source="lead_record", observed_value="A", effect="Context only.")
    b = a.model_copy(update={"observed_value": "B"})
    previous, current = pair({"evidence": [a, b]}, {"evidence": [b]})
    result = compare_decisions(previous, current)
    assert result.removed_evidence == [a] and not result.added_evidence
    assert result.evidence_changed and not result.evidence_provenance_changed


def test_policy_change_prevents_an_unqualified_improvement_claim():
    previous, current = pair({"decision_version": "historical_v0"}, {"opportunity_score": 90})
    result = compare_decisions(previous, current)
    assert result.policy_version_changed and result.overall_direction == "MIXED" and result.material_change


@pytest.mark.parametrize("before,after,delta", [(.3, .1, -.2), (.63, .88, .25), (.29, .3, .01), (1e-308, 0, -1e-308), (0, 1e-308, 1e-308)])
def test_confidence_decimal_subtraction_has_no_binary_artifact(before, after, delta):
    previous, current = pair({"confidence": before}, {"confidence": after})
    assert compare_decisions(previous, current).confidence_delta == delta


@pytest.mark.parametrize("field", ["organization_id", "lead_id"])
def test_domain_rejects_mismatched_tenant_or_lead(field):
    previous, current = pair(after={field: 2})
    with pytest.raises(ValueError, match="same tenant-owned lead"):
        compare_decisions(previous, current)


def test_reasons_only_change_is_reported_without_a_causal_or_material_claim():
    previous, current = pair(after={"reasons": ["Different explanation."]})
    result = compare_decisions(previous, current)
    assert result.reasons_changed and result.overall_direction == "MIXED" and not result.material_change
    assert not any("because" in x.lower() or "caused by" in x.lower() for x in result.explanations)


@pytest.mark.parametrize("with_history", [False, True])
def test_authenticated_comparison_no_history_latest_and_read_only(tenant_workspace, with_history):
    from backend.database.session import SessionLocal, engine
    from backend.services.lead_lifecycle_service import LeadLifecycleService
    from tests.api.test_tenant_leads import headers
    w = tenant_workspace
    lead, org = w["ids"]["leads"]["a"], w["ids"]["organizations"]["a"]
    client = w["clients"]["a"]
    previous = None
    if with_history:
        response = client.post(f"/api/leads/{lead}/opportunity-decisions", headers=headers(w, "a", csrf=True))
        assert response.status_code == 201
        previous = DecisionLedgerRecord.model_validate(response.json())
        with SessionLocal() as db:
            from backend.schemas.execution_principal import ExecutionPrincipal
            principal = ExecutionPrincipal.for_user(w["ids"]["users"]["a"], org, correlation_id="p2c-fixture")
            LeadLifecycleService(db).update_lifecycle(principal, lead_id=lead, organization_id=org, status="Meeting")
    before = snapshot(engine)
    for _ in range(2):
        response = client.get(f"/api/leads/{lead}/opportunity-decision/change", headers=headers(w, "a"))
        assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
        result = DecisionChangeResponse.model_validate(response.json())
        assert result.current_decision.lead_id == lead and result.current_decision.organization_id == org
        assert result.history.total == int(with_history) and result.history.limit == 5 and result.history.offset == 0
        if with_history:
            assert result.latest_recorded_decision == previous
            assert result.change == compare_decisions(previous, result.current_decision)
            assert result.change.readiness_score_delta > 0
        else:
            assert result.change is None and result.latest_recorded_decision is None and result.history.items == []
    assert snapshot(engine) == before
    for other in [w["ids"]["leads"]["b"], 9223372036854775807]:
        assert client.get(f"/api/leads/{other}/opportunity-decision/change", headers=headers(w, "a")).status_code == 404
    from fastapi.testclient import TestClient
    from backend.main import app
    with TestClient(app) as anonymous:
        assert anonymous.get(f"/api/leads/{lead}/opportunity-decision/change").status_code == 401
    assert snapshot(engine) == before


def test_service_fetches_current_once_bounded_latest_and_never_flushes(tenant_workspace):
    from backend.database.session import SessionLocal, engine
    from backend.services.decision_comparison_service import DecisionComparisonService
    w = tenant_workspace
    before = snapshot(engine)
    statements = []
    def collect(_c, _cursor, statement, *_args): statements.append(statement)
    def forbidden(*_args): raise AssertionError("Read comparison attempted settlement or flush")
    with SessionLocal() as db:
        event.listen(engine, "before_cursor_execute", collect)
        for name in ["before_commit", "before_flush", "after_rollback"]: event.listen(db, name, forbidden)
        try:
            result = DecisionComparisonService(db).get_change(w["ids"]["leads"]["a"], w["ids"]["organizations"]["a"])
            assert result is not None and len(statements) == 4
            assert all(s.lstrip().upper().startswith("SELECT") for s in statements)
        finally:
            event.remove(engine, "before_cursor_execute", collect)
            for name in ["before_commit", "before_flush", "after_rollback"]: event.remove(db, name, forbidden)
    assert snapshot(engine) == before
