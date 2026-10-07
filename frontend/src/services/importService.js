import api from "./api";

export function previewLeadCsv(file) {
  return api.post("/api/imports/leads/preview", file, {
    organization: true,
    headers: { "Content-Type": "text/csv" },
  });
}

export function confirmLeadImport(file, token) {
  return api.post("/api/imports/leads/confirm", file, {
    organization: true,
    headers: { "Content-Type": "text/csv", "X-Import-Preview-Token": token },
  });
}
