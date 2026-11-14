import api from "./api";

/** @param {import('../types/api').QueryParams} params @returns {Promise<import('../types/api').ReportOverview>} */
export const getReportOverview = (params) => api.get("/api/reports/v2/overview", { params, organization: true });
/** @param {import('../types/api').QueryParams} params @returns {Promise<Blob>} */
export const exportReport = (params) => api.get("/api/reports/v2/export.csv", { params, organization: true, responseType: "blob" });

/** @param {number} [limit] @returns {Promise<import('../types/api').LegacyReport>} */
export async function getDailyReport(limit = 5) {
  return api.get("/api/reports/daily", { params: { limit }, organization: true });
}

/** @param {number} [limit] @returns {Promise<import('../types/api').LegacyReport>} */
export async function getWeeklyReport(limit = 5) {
  return api.get("/api/reports/weekly", { params: { limit }, organization: true });
}

/** @param {number} [limit] @returns {Promise<import('../types/api').LegacyReport>} */
export async function getMonthlyReport(limit = 5) {
  return api.get("/api/reports/monthly", { params: { limit }, organization: true });
}

/** @returns {Promise<import('../types/api').ExecutiveReport>} */
export async function getExecutiveReport() {
  return api.get("/api/reports/executive", { organization: true });
}
