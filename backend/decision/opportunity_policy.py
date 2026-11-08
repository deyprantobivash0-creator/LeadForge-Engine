"""Pure Revenue Brain v1: stored assessments are estimates, never observed intent.

No target ICP, contact role, company size, or engagement feed exists in the
current model. Fit therefore means the existing company-fit assessment, not
verified ICP alignment. Missing/unsupported assessments are unknown, not facts.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from types import MappingProxyType

from pydantic import ValidationError

from backend.ai.schemas.lead_brain import LeadBrainResult
from backend.decision.lead_scorer import LeadScorer
from backend.schemas.opportunity_decision import (
    DecisionEvidence, DecisionRisk as Risk, MissingSignal as Missing,
    OpportunityDecision, RecommendedAction as Action,
)


@dataclass(frozen=True)
class OpportunityPolicy:
    version: str = "revenue_brain_v1"
    # Opportunity = .35 fit + .35 readiness + .20 qualification + .10 coverage.
    weights: tuple[int, ...] = (35, 35, 20, 10)
    readiness_weights: tuple[int, ...] = (70, 30)
    neutral_score: int = 40
    confidence_weights: tuple[float, ...] = (.15, .15, .20, .20, .20, .10)
    direct_quality: float = .8
    derived_quality: float = .4
    conflict_penalty: float = .25
    uncertain_penalty: float = .15
    low_confidence: float = .65
    strong_score: int = 70
    ready_score: int = 65
    low_score: int = 35
    low_fit: int = 30
    unqualified_intent: int = 30


POLICY = OpportunityPolicy()
LIFECYCLE_READINESS = MappingProxyType({
    "New": 0, "Qualified": 40, "Contacted": 60, "Meeting": 90, "Won": 0, "Lost": 0,
})
STAGES = ("company", "contact", "intent")
STAGE_MISSING = (Missing.COMPANY_ASSESSMENT, Missing.CONTACT_ASSESSMENT, Missing.INTENT_ASSESSMENT)


@dataclass(frozen=True)
class RevenueFeatures:
    lead_id: int
    organization_id: int
    company_present: bool
    contact_present: bool
    lifecycle: str | None
    stages: tuple[int | None, ...]
    quality: tuple[float, ...]
    qualification: int | None
    risks: tuple[Risk, ...]


def present(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def extract_features(lead, analysis) -> RevenueFeatures:
    """Copy only allowlisted scalar signals; never expose arbitrary stored text."""
    risks = []
    stages, quality, qualification = (None, None, None), (0., 0., 0.), None
    lifecycle = lead.status if lead.status in LIFECYCLE_READINESS else None
    if lifecycle is None:
        risks.append(Risk.UNKNOWN_LIFECYCLE)
    if lead.processing_status == "processing":
        risks.append(Risk.ANALYSIS_IN_PROGRESS)
    if analysis is not None:
        # Defense in depth for direct domain callers as well as scoped repositories.
        if analysis.organization_id != lead.organization_id or analysis.lead_id != lead.id:
            risks.append(Risk.INVALID_ANALYSIS)
        elif analysis.company != lead.company or analysis.email != lead.email:
            risks.append(Risk.STALE_ANALYSIS)
        else:
            try:
                result = LeadBrainResult.model_validate(analysis.result)
                score, priority = LeadScorer().score_components(*(getattr(result, s).score for s in STAGES))
                if (score != analysis.lead_score or priority != analysis.priority
                        or score != result.final_decision.lead_score
                        or priority != result.final_decision.priority):
                    raise ValueError("Inconsistent stored qualification")
                extracted, qualities = [], []
                for name in STAGES:
                    stage = getattr(result, name)
                    # Require actual existing backing fields even for a derived estimate.
                    supported = bool(stage.evidence) and all(
                        present(getattr(lead, e.field, None)) and
                        (e.source == "derived" or e.value == getattr(lead, e.field))
                        for e in stage.evidence
                    )
                    if stage.evidence and not supported:
                        risks.append(Risk.STALE_ANALYSIS)
                    extracted.append(stage.score if supported else None)
                    direct = sum(e.source == "lead_data" for e in stage.evidence)
                    qualities.append((POLICY.direct_quality if direct else POLICY.derived_quality) if supported else 0.)
                stages, quality = tuple(extracted), tuple(qualities)
                # A final score with unsupported components is not a trusted factor.
                qualification = score if all(s is not None for s in stages) else None
            except (ValidationError, ValueError, TypeError):
                risks.append(Risk.INVALID_ANALYSIS)
    return RevenueFeatures(lead.id, lead.organization_id, present(lead.company), present(lead.email),
                           lifecycle, stages, quality, qualification, tuple(dict.fromkeys(risks)))


def weighted(values, weights):
    value = sum(Decimal(v) * w for v, w in zip(values, weights)) / 100
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def evaluate(features: RevenueFeatures) -> OpportunityDecision:
    p, f = POLICY, features
    company, contact, intent = f.stages
    missing = []
    if not f.company_present:
        missing.append(Missing.COMPANY_PROFILE)
    if not f.contact_present:
        missing.append(Missing.CONTACT_DETAILS)
    missing.extend(m for m, score in zip(STAGE_MISSING, f.stages) if score is None)
    if f.lifecycle is None:
        missing.append(Missing.LIFECYCLE_STATE)
    risks = list(f.risks)
    if missing:
        risks.append(Risk.INSUFFICIENT_DATA)
    # Lifecycle progress and an extremely low inferred intent need reconciliation.
    conflict = (f.lifecycle in {"Qualified", "Contacted", "Meeting"}
                and intent is not None and intent < p.unqualified_intent)
    if conflict:
        risks.append(Risk.CONFLICTING_SIGNALS)
    if company is not None and company < p.low_fit:
        risks.append(Risk.LOW_ASSESSED_FIT)
    availability = (f.company_present, f.contact_present, *(s is not None for s in f.stages), f.lifecycle is not None)
    qualities = (1., 1., *f.quality, 1.)
    confidence = sum(w * available * q for w, available, q in zip(p.confidence_weights, availability, qualities))
    confidence -= p.conflict_penalty if conflict else 0
    uncertain = any(r in risks for r in (Risk.STALE_ANALYSIS, Risk.INVALID_ANALYSIS, Risk.UNKNOWN_LIFECYCLE, Risk.ANALYSIS_IN_PROGRESS))
    confidence -= p.uncertain_penalty if uncertain else 0
    confidence = round(max(0., min(1., confidence)), 2)
    if confidence < p.low_confidence:
        risks.append(Risk.LOW_CONFIDENCE)
    fit = company if company is not None else p.neutral_score
    readiness = weighted((intent if intent is not None else p.neutral_score,
                          LIFECYCLE_READINESS.get(f.lifecycle, p.neutral_score)), p.readiness_weights)
    coverage = weighted(tuple(int(a) * 100 for a in availability), tuple(int(w * 100) for w in p.confidence_weights))
    qualification = f.qualification if f.qualification is not None else p.neutral_score
    opportunity = weighted((fit, readiness, qualification, coverage), p.weights)
    closed = f.lifecycle in {"Won", "Lost"}
    if closed:
        opportunity = 0
    review = bool(missing or conflict or uncertain or confidence < p.low_confidence)
    if closed:
        action = Action.DEPRIORITIZE
    elif conflict or uncertain:
        action = Action.HUMAN_REVIEW
    elif missing:
        action = Action.RESEARCH_MORE
    elif review:
        action = Action.HUMAN_REVIEW
    elif fit < p.low_fit or opportunity < p.low_score:
        action = Action.DEPRIORITIZE
    elif opportunity >= p.strong_score and readiness >= p.ready_score:
        action = Action.PREPARE_OUTREACH
    elif readiness < p.ready_score:
        action = Action.QUALIFY
    else:
        action = Action.NURTURE
    reasons = [
        (f"Stored company-fit assessment is {fit}/100; this is an estimate, not verified ICP alignment."
         if company is not None else f"Company-fit assessment is unavailable; policy uses a neutral prior of {p.neutral_score}/100."),
        (f"Readiness combines stored intent estimate {intent}/100 with lifecycle {f.lifecycle or 'unknown'}; no observed engagement is available."
         if intent is not None else
         f"Intent estimate is unavailable; readiness uses a neutral policy prior of {p.neutral_score}/100 with lifecycle {f.lifecycle or 'unknown'}; no observed engagement is available."),
        (f"Opportunity uses the validated stored qualification score of {qualification}/100."
         if f.qualification is not None else
         f"Qualification is unavailable; opportunity uses a neutral policy prior of {p.neutral_score}/100."),
        "Opportunity combines fit, readiness, the disclosed qualification factor, and signal coverage; it does not overwrite the legacy score.",
        "Confidence reflects available signal coverage and assessment provenance; absent signals do not count as evidence.",
    ]
    if f.lifecycle is None:
        reasons.append(f"Lifecycle state is unavailable; readiness uses a neutral policy proxy of {p.neutral_score}/100.")
    if missing:
        reasons.append("Missing signals limit this decision; research is required before acting.")
    if conflict:
        reasons.append("Advanced lifecycle conflicts with low stored intent assessment; a human must reconcile them.")
    if Risk.LOW_ASSESSED_FIT in risks:
        reasons.append("The stored company-fit estimate is low; other positive signals do not establish strong fit.")
    if uncertain:
        reasons.append("Invalid, changed, unknown, or in-progress context requires human review.")
    if closed:
        reasons.append("The lead is closed; it is not an active opportunity for new outreach.")
    elif action == Action.PREPARE_OUTREACH:
        reasons.append("Opportunity and readiness meet preparation thresholds; this recommendation executes no outreach.")
    evidence = [
        DecisionEvidence(signal="company_profile", observed_value="present" if f.company_present else "missing",
                         effect="Presence supports coverage only; no target segment is inferred.", source="lead_record"),
        DecisionEvidence(signal="contact_details", observed_value="present" if f.contact_present else "missing",
                         effect="Presence supports coverage only; contact role and deliverability are unknown.", source="lead_record"),
        DecisionEvidence(signal="lifecycle", observed_value=f.lifecycle or "unknown",
                         effect=(f"Lifecycle readiness proxy: {LIFECYCLE_READINESS[f.lifecycle]}/100; not measured intent."
                                 if f.lifecycle is not None else
                                 f"Lifecycle state is unavailable; policy uses a neutral readiness proxy of {p.neutral_score}/100."),
                         source="lead_record" if f.lifecycle is not None else "policy"),
    ]
    fallback_effects = {
        "company": f"Company-fit assessment is unavailable; policy uses a neutral fit prior of {p.neutral_score}/100.",
        "contact": "Contact assessment is unavailable; qualification uses a policy prior until all components are supported.",
        "intent": f"Intent estimate is unavailable; policy uses a neutral readiness prior of {p.neutral_score}/100.",
    }
    for name, score, quality in zip(STAGES, f.stages, f.quality):
        evidence.append(DecisionEvidence(signal=f"{name}_assessment", observed_value=str(score) if score is not None else "unavailable",
            effect=(f"Stored estimate; provenance quality {quality:.1f}. Unsupported evidence is excluded."
                    if score is not None else fallback_effects[name]),
            source="stored_assessment" if score is not None else "policy"))
    evidence.extend([
        DecisionEvidence(signal="qualification", observed_value=str(f.qualification) if f.qualification is not None else "unavailable",
                         effect=(f"Validated stored qualification score contributes {qualification}/100."
                                 if f.qualification is not None else
                                 f"Qualification is unavailable; policy uses a neutral prior of {p.neutral_score}/100."),
                         source="stored_assessment" if f.qualification is not None else "policy"),
        DecisionEvidence(signal="opportunity_composition", observed_value=f"fit={fit}; readiness={readiness}; qualification={qualification}; coverage={coverage}",
                         effect="Weights 35/35/20/10, half-up rounding; closed lifecycle overrides opportunity to zero.", source="policy"),
    ])
    return OpportunityDecision(lead_id=f.lead_id, organization_id=f.organization_id,
        decision_version=p.version, opportunity_score=opportunity, fit_score=fit, readiness_score=readiness,
        confidence=confidence, recommended_action=action, human_review_required=review, reasons=reasons,
        evidence=evidence, risk_flags=list(dict.fromkeys(risks)), missing_signals=missing,
        generated_at=datetime.now(timezone.utc))
