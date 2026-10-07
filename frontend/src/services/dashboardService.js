import api from "./api";

export const getDashboardOverview = (params = {}) => api.get("/api/dashboard/v2/overview", { params, organization: true });
