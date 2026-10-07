import api from "./api";

export const getReportOverview = (params) => api.get("/api/reports/v2/overview", { params, organization: true });
export const exportReport = (params) => api.get("/api/reports/v2/export.csv", { params, organization: true, responseType: "blob" });

export async function getDailyReport(limit = 5) {
  return api.get("/api/reports/daily", { params: { limit }, organization: true });
}

export async function getWeeklyReport(limit = 5) {
  return api.get("/api/reports/weekly", { params: { limit }, organization: true });
}

export async function getMonthlyReport(limit = 5) {
  return api.get("/api/reports/monthly", { params: { limit }, organization: true });
}

export async function getExecutiveReport() {
  return api.get("/api/reports/executive", { organization: true });
}
