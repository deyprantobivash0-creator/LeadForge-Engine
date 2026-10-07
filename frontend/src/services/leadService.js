import api from "./api";

export const getLeads = (params = {}) => api.get("/api/leads/", { params, organization: true });
export const getLead = (leadId) => api.get(`/api/leads/${leadId}`, { organization: true });
export const searchLeads = (params = {}) => api.get("/api/leads/search", { params, organization: true });
export const getFollowUps = (params = {}) => api.get("/api/leads/follow-ups", { params, organization: true });
export const createLead = (payload) => api.post("/api/leads/", payload, { organization: true });
export const updateLeadLifecycle = (leadId, payload) => api.patch(`/api/leads/${leadId}/lifecycle`, payload, { organization: true });
export const getLeadIntelligence = (leadId) => api.get(`/api/leads/${leadId}/intelligence`, { organization: true });
export const getAnalysisHistory = (leadId, params = {}) => api.get(`/api/leads/${leadId}/analyses`, { params, organization: true });
export const processLead = (leadId) => api.post(`/api/leads/${leadId}/process`, {}, { organization: true });
