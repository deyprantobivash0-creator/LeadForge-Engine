import api from "./api";

/** @param {import('../types/api').QueryParams} [params] @returns {Promise<import('../types/api').LeadPage>} */
export const getLeads = (params = {}) => api.get("/api/leads/", { params, organization: true });
/** @param {import('../types/api').ID} leadId @returns {Promise<import('../types/api').LeadDetail>} */
export const getLead = (leadId) => api.get(`/api/leads/${leadId}`, { organization: true });
/** @param {import('../types/api').QueryParams} [params] @returns {Promise<import('../types/api').LeadPage>} */
export const searchLeads = (params = {}) => api.get("/api/leads/search", { params, organization: true });
/** @param {import('../types/api').QueryParams} [params] @returns {Promise<import('../types/api').LeadPage>} */
export const getFollowUps = (params = {}) => api.get("/api/leads/follow-ups", { params, organization: true });
/** @param {import('../types/api').LeadCreate} payload @returns {Promise<import('../types/api').Lead>} */
export const createLead = (payload) => api.post("/api/leads/", payload, { organization: true });
/** @param {import('../types/api').ID} leadId @param {import('../types/api').LifecycleUpdate} payload @returns {Promise<import('../types/api').Lead>} */
export const updateLeadLifecycle = (leadId, payload) => api.patch(`/api/leads/${leadId}/lifecycle`, payload, { organization: true });
/** @param {import('../types/api').ID} leadId @returns {Promise<import('../types/api').LeadIntelligence>} */
export const getLeadIntelligence = (leadId) => api.get(`/api/leads/${leadId}/intelligence`, { organization: true });
/** @param {import('../types/api').ID} leadId @param {import('../types/api').QueryParams} [params] @returns {Promise<import('../types/api').AnalysisHistory>} */
export const getAnalysisHistory = (leadId, params = {}) => api.get(`/api/leads/${leadId}/analyses`, { params, organization: true });
/** @param {import('../types/api').ID} leadId @returns {Promise<import('../types/api').LeadProcessing>} */
export const processLead = (leadId) => api.post(`/api/leads/${leadId}/process`, {}, { organization: true });
