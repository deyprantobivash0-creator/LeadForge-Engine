/**
 * Revenue Brain transport contracts in the existing JavaScript/JSDoc project.
 * @typedef {'RESEARCH_MORE'|'HUMAN_REVIEW'|'QUALIFY'|'PREPARE_OUTREACH'|'NURTURE'|'DEPRIORITIZE'} Recommendation
 * @typedef {'IMPROVED'|'DECLINED'|'MIXED'|'UNCHANGED'} ChangeDirection
 * @typedef {'INSUFFICIENT_DATA'|'LOW_CONFIDENCE'|'CONFLICTING_SIGNALS'|'INVALID_ANALYSIS'|'STALE_ANALYSIS'|'UNKNOWN_LIFECYCLE'|'LOW_ASSESSED_FIT'|'ANALYSIS_IN_PROGRESS'} RiskFlag
 * @typedef {'company_profile'|'contact_details'|'company_assessment'|'contact_assessment'|'intent_assessment'|'lifecycle_state'} MissingSignal
 * @typedef {{signal:string, observed_value:string, effect:string, source:'lead_record'|'stored_assessment'|'policy'}} DecisionEvidence
 * @typedef {{organization_id:number, lead_id:number, decision_version:string, opportunity_score:number, fit_score:number, readiness_score:number, confidence:number, recommended_action:Recommendation, human_review_required:boolean, reasons:string[], evidence:DecisionEvidence[], risk_flags:RiskFlag[], missing_signals:MissingSignal[]}} DecisionContent
 * @typedef {DecisionContent & {generated_at:string}} CurrentDecision
 * @typedef {DecisionContent & {id:string, decision_generated_at:string, recorded_at:string}} LedgerRecord
 * @typedef {{items:LedgerRecord[], total:number, limit:number, offset:number}} HistoryPage
 * @typedef {'opportunity_threshold'|'fit_threshold'|'readiness_threshold'|'confidence_threshold'|'recommendation'|'human_review'|'risks'|'missing_signals'|'evidence_provenance'|'policy_version'} MaterialFactor
 * @typedef {Object} DecisionChange
 * @property {'decision_change_v1'} comparison_version
 * @property {string} from_decision_id
 * @property {string} from_recorded_at
 * @property {'current_computed'} to_kind
 * @property {string} to_generated_at
 * @property {string} previous_policy_version
 * @property {string} current_policy_version
 * @property {boolean} policy_version_changed
 * @property {number} opportunity_score_delta
 * @property {number} fit_score_delta
 * @property {number} readiness_score_delta
 * @property {number} confidence_delta
 * @property {boolean} recommendation_changed
 * @property {Recommendation} previous_recommendation
 * @property {Recommendation} current_recommendation
 * @property {boolean} human_review_changed
 * @property {boolean} previous_human_review_required
 * @property {boolean} current_human_review_required
 * @property {RiskFlag[]} added_risk_flags
 * @property {RiskFlag[]} removed_risk_flags
 * @property {MissingSignal[]} added_missing_signals
 * @property {MissingSignal[]} resolved_missing_signals
 * @property {boolean} evidence_changed
 * @property {boolean} evidence_provenance_changed
 * @property {DecisionEvidence[]} added_evidence
 * @property {DecisionEvidence[]} removed_evidence
 * @property {boolean} reasons_changed
 * @property {string[]} added_reasons
 * @property {string[]} removed_reasons
 * @property {ChangeDirection} overall_direction
 * @property {boolean} material_change
 * @property {MaterialFactor[]} material_factors
 * @property {string[]} explanations
 * @typedef {{current_decision:CurrentDecision, latest_recorded_decision:LedgerRecord|null, change:DecisionChange|null, history:HistoryPage}} DecisionChangeResponse
 */
export {};
