import api from "./api";

/** @param {Blob} file @returns {Promise<import('../types/api').ImportPreview>} */
export function previewLeadCsv(file) {
  return api.post("/api/imports/leads/preview", file, {
    organization: true,
    headers: { "Content-Type": "text/csv" },
  });
}

/** @param {Blob} file @param {string} token @returns {Promise<import('../types/api').ImportResult>} */
export function confirmLeadImport(file, token) {
  return api.post("/api/imports/leads/confirm", file, {
    organization: true,
    headers: { "Content-Type": "text/csv", "X-Import-Preview-Token": token },
  });
}
