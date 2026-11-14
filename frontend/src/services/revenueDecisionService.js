import api from "./api";

/** @param {number|string} leadId @returns {Promise<import('../types/revenueDecision').DecisionChangeResponse>} */
export const getDecisionChange = (leadId) => api.get(`/api/leads/${leadId}/opportunity-decision/change`, { organization: true });

/** @param {number|string} leadId @param {{limit:number,offset:number}} page @returns {Promise<import('../types/revenueDecision').HistoryPage>} */
export const getDecisionHistory = (leadId, page) => api.get(`/api/leads/${leadId}/opportunity-decisions`, { organization: true, params: page });

/** @param {number|string} leadId @returns {Promise<import('../types/revenueDecision').LedgerRecord>} */
export const recordCurrentDecision = (leadId) => api.post(`/api/leads/${leadId}/opportunity-decisions`, {}, { organization: true });
