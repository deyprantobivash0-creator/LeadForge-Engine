import api from "./api";
/** @typedef {'Contacted'|'Qualified'|'Meeting'|'Won'|'Lost'} OutcomeKind */
/** @typedef {{kind:OutcomeKind,observed_at:string,note?:string|null}} OutcomeInput */
/** @typedef {OutcomeInput & {id:string,organization_id:number,lead_id:number,decision_id:string,recorded_by_user_id:number,recorded_at:string,source:string}} OutcomeRecord */
/** @typedef {{items:OutcomeRecord[],total:number,limit:number,offset:number,effectiveness:string}} OutcomeHistory */
/** @param {number|string} lead @param {string} decision @param {number} offset @returns {Promise<OutcomeHistory>} */
export const getOutcomes = (lead, decision, offset = 0) => api.get(`/api/leads/${lead}/opportunity-decisions/${decision}/outcomes`, { organization: true, params: { limit: 20, offset } });
/** @param {number|string} lead @param {string} decision @param {OutcomeInput} value @returns {Promise<OutcomeRecord>} */
export const recordOutcome = (lead, decision, value) => api.post(`/api/leads/${lead}/opportunity-decisions/${decision}/outcomes`, value, { organization: true });
