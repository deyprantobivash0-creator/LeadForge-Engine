const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
const CSRF_COOKIE_NAME = import.meta.env.VITE_CSRF_COOKIE_NAME || "leadforge_csrf";
const CSRF_HEADER_NAME = import.meta.env.VITE_CSRF_HEADER_NAME || "X-CSRF-Token";
let selectedOrganizationId = null;
let onUnauthorized = () => {};
let onForbidden = () => {};

export class ApiError extends Error {
  constructor(status, message, details = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.details = details;
  }
}

export function configureApi({ organizationId, unauthorized, forbidden }) {
  selectedOrganizationId = organizationId;
  onUnauthorized = unauthorized;
  onForbidden = forbidden;
}

function readCookie(name) {
  const prefix = `${name}=`;
  const part = document.cookie.split("; ").find((cookie) => cookie.startsWith(prefix));
  return part ? decodeURIComponent(part.slice(prefix.length)) : null;
}

async function request(endpoint, { method = "GET", data, params, organization = false, handleAuth = true, responseType = "json", headers: extraHeaders = {} } = {}) {
  if (organization && !selectedOrganizationId) {
    throw new ApiError(400, "Select a workspace to continue.");
  }
  const url = new URL(`${API_BASE_URL}${endpoint}`, window.location.origin);
  for (const [key, value] of Object.entries(params || {})) {
    if (value !== undefined && value !== null && value !== "") url.searchParams.set(key, String(value));
  }
  const headers = { ...extraHeaders };
  if (data !== undefined && !(data instanceof Blob) && !(data instanceof FormData)) headers["Content-Type"] = "application/json";
  if (organization) headers["X-Organization-ID"] = String(selectedOrganizationId);
  if (!["GET", "HEAD"].includes(method)) {
    const csrf = readCookie(CSRF_COOKIE_NAME);
    if (csrf) headers[CSRF_HEADER_NAME] = csrf;
  }
  let response;
  try {
    response = await fetch(url, {
      method,
      credentials: "include",
      headers,
      ...(data !== undefined ? { body: data instanceof Blob || data instanceof FormData ? data : JSON.stringify(data) } : {}),
    });
  } catch {
    throw new ApiError(0, "Cannot reach the server. Check the connection and try again.");
  }
  const body = response.status === 204 ? null : response.ok && responseType === "blob" ? await response.blob() : await response.json().catch(() => null);
  if (!response.ok) {
    if (handleAuth && response.status === 401) onUnauthorized();
    if (handleAuth && organization && response.status === 403) onForbidden();
    const message = body?.error?.message || (typeof body?.detail === "string" ? body.detail : null) || `Request failed (${response.status}).`;
    throw new ApiError(response.status, message, body?.error?.details || body?.detail || null);
  }
  return body;
}

export const api = {
  get: (endpoint, options) => request(endpoint, { ...options, method: "GET" }),
  post: (endpoint, data, options) => request(endpoint, { ...options, method: "POST", data }),
  put: (endpoint, data, options) => request(endpoint, { ...options, method: "PUT", data }),
  patch: (endpoint, data, options) => request(endpoint, { ...options, method: "PATCH", data }),
  delete: (endpoint, options) => request(endpoint, { ...options, method: "DELETE" }),
};

export default api;
