"""Canonical, deterministic comparisons; no SQL, clock, randomness or providers."""

from decimal import Decimal
import unicodedata

from backend.schemas.decision_change import ChangeDirection, DecisionChange, MaterialFactor
from backend.schemas.decision_ledger import DecisionLedgerRecord
from backend.schemas.opportunity_decision import OpportunityDecision


MATERIAL_OPPORTUNITY_POINTS = 5
MATERIAL_COMPONENT_POINTS = 10
MATERIAL_CONFIDENCE = Decimal("0.05")
HISTORY_PREVIEW_LIMIT = 5


def _text(value):
    return unicodedata.normalize("NFC", " ".join(value.split()))


def _evidence(entries):
    # Structured identity, not rendered display text. Deduplicate semantically
    # identical entries, while retaining distinct values for the same signal.
    return {(_text(e.signal), e.source, _text(e.observed_value), _text(e.effect)): e for e in entries}


def _set_diff(before, after):
    return sorted(set(after) - set(before)), sorted(set(before) - set(after))


def compare_decisions(previous: DecisionLedgerRecord, current: OpportunityDecision) -> DecisionChange:
    if type(previous) is not DecisionLedgerRecord or type(current) is not OpportunityDecision:
        raise ValueError("Typed decisions are required.")
    if (previous.organization_id, previous.lead_id) != (current.organization_id, current.lead_id):
        raise ValueError("Decisions must belong to the same tenant-owned lead.")

    opportunity = current.opportunity_score - previous.opportunity_score
    fit = current.fit_score - previous.fit_score
    readiness = current.readiness_score - previous.readiness_score
    confidence = Decimal(str(current.confidence)) - Decimal(str(previous.confidence))
    added_risks, removed_risks = _set_diff(previous.risk_flags, current.risk_flags)
    added_missing, resolved_missing = _set_diff(previous.missing_signals, current.missing_signals)
    before_evidence, after_evidence = _evidence(previous.evidence), _evidence(current.evidence)
    added_keys, removed_keys = _set_diff(before_evidence, after_evidence)
    provenance = {key[:2] for key in before_evidence} != {key[:2] for key in after_evidence}
    added_reasons, removed_reasons = _set_diff(map(_text, previous.reasons), map(_text, current.reasons))
    recommendation = previous.recommended_action != current.recommended_action
    review = previous.human_review_required != current.human_review_required
    policy = previous.decision_version != current.decision_version
    evidence = bool(added_keys or removed_keys)
    reasons = bool(added_reasons or removed_reasons)

    # No ranking is invented for recommendations or evidence text. Different
    # policy/provenance contexts require a conservative MIXED interpretation.
    positive = any(d > 0 for d in (opportunity, fit, readiness, confidence)) or bool(
        removed_risks or resolved_missing or (review and not current.human_review_required))
    negative = any(d < 0 for d in (opportunity, fit, readiness, confidence)) or bool(
        added_risks or added_missing or (review and current.human_review_required))
    semantic_change = positive or negative or recommendation or evidence or reasons or policy
    if policy or provenance or (positive and negative):
        direction = ChangeDirection.MIXED
    elif positive:
        direction = ChangeDirection.IMPROVED
    elif negative:
        direction = ChangeDirection.DECLINED
    else:
        direction = ChangeDirection.MIXED if semantic_change else ChangeDirection.UNCHANGED

    factors = []
    for applies, factor in (
        (abs(opportunity) >= MATERIAL_OPPORTUNITY_POINTS, MaterialFactor.OPPORTUNITY),
        (abs(fit) >= MATERIAL_COMPONENT_POINTS, MaterialFactor.FIT),
        (abs(readiness) >= MATERIAL_COMPONENT_POINTS, MaterialFactor.READINESS),
        (abs(confidence) >= MATERIAL_CONFIDENCE, MaterialFactor.CONFIDENCE),
        (recommendation, MaterialFactor.RECOMMENDATION), (review, MaterialFactor.HUMAN_REVIEW),
        (bool(added_risks or removed_risks), MaterialFactor.RISKS),
        (bool(added_missing or resolved_missing), MaterialFactor.MISSING_SIGNALS),
        (provenance, MaterialFactor.PROVENANCE), (policy, MaterialFactor.POLICY),
    ):
        if applies:
            factors.append(factor)

    explanations = []
    for label, delta in (("Opportunity", opportunity), ("Fit", fit), ("Readiness", readiness)):
        if delta:
            explanations.append(f"{label} {'increased' if delta > 0 else 'decreased'} by {abs(delta)} points.")
    if confidence:
        explanations.append(f"Coverage confidence {'increased' if confidence > 0 else 'decreased'} by {abs(confidence):g}; this is not a probability of sale.")
    if recommendation:
        explanations.append(f"Recommendation changed from {previous.recommended_action.value} to {current.recommended_action.value}. No action is implied.")
    if review:
        explanations.append("Human review is now required." if current.human_review_required else "Human review is no longer required by this decision.")
    if added_risks or removed_risks:
        explanations.append(f"Risk flags: {len(added_risks)} added, {len(removed_risks)} removed.")
    if added_missing or resolved_missing:
        explanations.append(f"Missing signals: {len(added_missing)} newly missing, {len(resolved_missing)} resolved.")
    if evidence:
        explanations.append("Changes include different structured evidence; stored estimates remain estimates, and neutral defaults are not observed signals.")
    if provenance:
        explanations.append("Available evidence sources changed; direction is mixed rather than assuming the contexts are equivalent.")
    if policy:
        explanations.append("Policy versions differ; score deltas do not by themselves establish improvement or decline.")
    if reasons:
        explanations.append("The decision explanations changed; these differences do not establish causality.")
    if not explanations:
        explanations.append("No semantic decision changes. Computation and recording timestamps may differ.")

    return DecisionChange(
        from_decision_id=previous.id, from_recorded_at=previous.recorded_at,
        to_generated_at=current.generated_at, previous_policy_version=previous.decision_version,
        current_policy_version=current.decision_version, policy_version_changed=policy,
        opportunity_score_delta=opportunity, fit_score_delta=fit, readiness_score_delta=readiness,
        confidence_delta=float(confidence), recommendation_changed=recommendation,
        previous_recommendation=previous.recommended_action, current_recommendation=current.recommended_action,
        human_review_changed=review, previous_human_review_required=previous.human_review_required,
        current_human_review_required=current.human_review_required, added_risk_flags=added_risks,
        removed_risk_flags=removed_risks, added_missing_signals=added_missing,
        resolved_missing_signals=resolved_missing, evidence_changed=evidence,
        evidence_provenance_changed=provenance, added_evidence=[after_evidence[k] for k in added_keys],
        removed_evidence=[before_evidence[k] for k in removed_keys], reasons_changed=reasons,
        added_reasons=added_reasons, removed_reasons=removed_reasons, overall_direction=direction,
        material_change=bool(factors), material_factors=factors, explanations=explanations,
    )
