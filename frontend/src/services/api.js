const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
const CSRF_COOKIE_NAME = import.meta.env.VITE_CSRF_COOKIE_NAME || "leadforge_csrf";
const CSRF_HEADER_NAME = import.meta.env.VITE_CSRF_HEADER_NAME || "X-CSRF-Token";
let selectedOrganizationId = null;
let onUnauthorized = () => {};
let onForbidden = () => {};

export class ApiError extends Error {
  constructor(status, message, details = null, requestId = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.details = details;
    this.requestId = requestId;
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
  const requestOrganizationId = selectedOrganizationId;
  let response;
  let body;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 90000);
  try {
    response = await fetch(url, {
      method,
      signal: controller.signal,
      credentials: "include",
      headers,
      ...(data !== undefined ? { body: data instanceof Blob || data instanceof FormData ? data : JSON.stringify(data) } : {}),
    });
    body = response.status === 204 ? null : response.ok && responseType === "blob" ? await response.blob() : await response.json().catch(error => { if (controller.signal.aborted) throw error; return null; });
  } catch {
    throw new ApiError(0, controller.signal.aborted ? "The request took too long. Refresh to check its result before trying again." : "Cannot reach the server. Check the connection and try again.");
  } finally {
    clearTimeout(timer);
  }
  if (!response.ok) {
    if (handleAuth && response.status === 401) onUnauthorized();
    if (handleAuth && organization && requestOrganizationId === selectedOrganizationId && response.status === 403) onForbidden();
    const defaults = { 401: "Sign in again to continue.", 403: "You do not have access to this action in the selected workspace.", 404: "This record is unavailable in the selected workspace.", 409: "This action conflicts with the current record. Refresh and try again.", 422: "Check the highlighted fields and try again.", 429: "Too many requests. Wait a minute and try again." };
    const message = response.status >= 500 ? "The service could not complete this request. Try again shortly." : response.status === 422 && (!body?.error?.message || body.error.message === "Request validation failed.") && typeof body?.detail !== "string" ? defaults[422] : body?.error?.message || (typeof body?.detail === "string" ? body.detail : null) || defaults[response.status] || "The request could not be completed. Try again.";
    throw new ApiError(response.status, message, body?.error?.details || body?.detail || null, response.headers.get("X-Request-ID"));
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
