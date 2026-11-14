// Explicitly synthetic transport fixtures. Business comparison lives in Python.
/** @type {import('../../src/types/revenueDecision').CurrentDecision} */
export const currentDecision = {
  organization_id: 1, lead_id: 1, decision_version: "revenue_brain_v1",
  opportunity_score: 95, fit_score: 95, readiness_score: 94, confidence: .88,
  recommended_action: "PREPARE_OUTREACH", human_review_required: false,
  reasons: ["Stored company assessment estimates fit at 95/100; this is not verified ICP alignment.", "Stored intent estimate is 95/100; no observed engagement or buying event is available."],
  evidence: [
    { signal: "company_assessment", observed_value: "95/100", source: "stored_assessment", effect: "Stored fit estimate, not externally confirmed fit." },
    { signal: "intent_assessment", observed_value: "95/100", source: "stored_assessment", effect: "Stored intent estimate, not verified buyer intent." },
  ],
  risk_flags: [], missing_signals: [], generated_at: "2026-11-11T10:00:00Z",
};

/** @param {number} index @returns {import('../../src/types/revenueDecision').LedgerRecord} */
export function recordedDecision(index) {
  const { generated_at, ...content } = currentDecision;
  return { ...content, id: `00000000-0000-4000-8000-${String(index).padStart(12, "0")}`,
    decision_generated_at: generated_at, recorded_at: `2026-11-11T11:${String(index).padStart(2, "0")}:00Z` };
}

/** @param {import('../../src/types/revenueDecision').LedgerRecord[]} records @param {boolean} mixed @returns {import('../../src/types/revenueDecision').DecisionChangeResponse} */
export function decisionResponse(records, mixed = false) {
  /** @type {import('../../src/types/revenueDecision').LedgerRecord[]} */
  const historyRecords = mixed && records.length ? [{ ...records[0], decision_version: "fixture_previous_policy",
    opportunity_score: 87, fit_score: 92, readiness_score: 82, confidence: .93,
    recommended_action: "QUALIFY", human_review_required: true, risk_flags: ["LOW_CONFIDENCE"], missing_signals: ["intent_assessment"],
    evidence: [{ signal: "intent_assessment", source: "policy", observed_value: "Neutral 40", effect: "No stored intent estimate is available; this factor is treated neutrally." }],
  }, ...records.slice(1)] : records;
  const latest = historyRecords[0] || null;
  return { current_decision: currentDecision, latest_recorded_decision: latest,
    history: { items: historyRecords.slice(0, 5), total: records.length, limit: 5, offset: 0 },
    change: latest ? {
      comparison_version: "decision_change_v1", from_decision_id: latest.id, from_recorded_at: latest.recorded_at,
      to_kind: "current_computed", to_generated_at: currentDecision.generated_at,
      previous_policy_version: latest.decision_version, current_policy_version: currentDecision.decision_version, policy_version_changed: mixed,
      opportunity_score_delta: mixed ? 8 : 0, fit_score_delta: mixed ? 3 : 0, readiness_score_delta: mixed ? 12 : 0, confidence_delta: mixed ? -.05 : 0,
      recommendation_changed: mixed, previous_recommendation: mixed ? "QUALIFY" : currentDecision.recommended_action, current_recommendation: currentDecision.recommended_action,
      human_review_changed: mixed, previous_human_review_required: mixed, current_human_review_required: false,
      added_risk_flags: [], removed_risk_flags: mixed ? ["LOW_CONFIDENCE"] : [],
      added_missing_signals: [], resolved_missing_signals: mixed ? ["intent_assessment"] : [],
      evidence_changed: mixed, evidence_provenance_changed: mixed,
      added_evidence: mixed ? currentDecision.evidence : [],
      removed_evidence: mixed ? [{ signal: "intent_assessment", source: "policy", observed_value: "Neutral 40", effect: "No stored intent estimate is available; this factor is treated neutrally." }] : [],
      reasons_changed: false, added_reasons: [], removed_reasons: [], overall_direction: mixed ? "MIXED" : "UNCHANGED",
      material_change: mixed, material_factors: mixed ? ["opportunity_threshold", "readiness_threshold", "confidence_threshold", "recommendation", "human_review", "risks", "missing_signals", "evidence_provenance"] : [],
      explanations: [mixed ? "Changes include higher scores and lower coverage confidence; no action outcome or causal attribution is implied." : "No semantic decision changes."],
    } : null };
}
