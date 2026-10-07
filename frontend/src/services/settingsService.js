import api from "./api";

export const getSettingsOverview = () => api.get("/api/settings/overview", { organization: true });
