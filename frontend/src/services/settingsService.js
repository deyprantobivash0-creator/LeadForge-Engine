import api from "./api";

/** @returns {Promise<import('../types/api').SettingsOverview>} */
export const getSettingsOverview = () => api.get("/api/settings/overview", { organization: true });
