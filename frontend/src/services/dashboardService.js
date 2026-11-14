import api from "./api";

/** @param {import('../types/api').QueryParams} [params] @returns {Promise<import('../types/api').DashboardOverview>} */
export const getDashboardOverview = (params = {}) => api.get("/api/dashboard/v2/overview", { params, organization: true });
