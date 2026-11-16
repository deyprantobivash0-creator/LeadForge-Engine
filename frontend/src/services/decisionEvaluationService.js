import api from "./api";
/** @typedef {{eligible:number,evaluated:number,pending:number,positive:number,negative:number,inconclusive:number}} EvidenceCounts */
/** @typedef {EvidenceCounts & {policy_version:'latest_observation_v1',window:'all_time',coverage:number|null,evidence_context:'No outcome evidence'|'Limited evidence',categories:(EvidenceCounts & {recommendation:import('../types/revenueDecision').Recommendation})[]}} Evaluation */
/** @typedef {{decision_id:string,lead_id:number,recommendation:import('../types/revenueDecision').Recommendation,decision_recorded_at:string,outcome_id:string|null,kind:import('./decisionOutcomeService').OutcomeKind|null,observed_at:string|null,outcome_recorded_at:string|null}} EvidenceRow */
/** @typedef {{items:EvidenceRow[],offset:number,limit:number,has_more:boolean}} EvidencePage */
/** @returns {Promise<Evaluation>} */
export const getEvaluation = () => api.get("/api/dashboard/decision-evaluation", { organization: true });
/** @param {number} offset @returns {Promise<EvidencePage>} */
export const getEvaluationEvidence = offset => api.get("/api/dashboard/decision-evaluation/evidence", { organization: true, params: { offset, limit: 20 } });
