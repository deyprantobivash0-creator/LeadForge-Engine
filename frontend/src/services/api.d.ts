/** Static contract for the existing parsed-JSON transport; runtime is api.js. */
export interface RequestOptions {
  organization?: boolean;
  handleAuth?: boolean;
  params?: Record<string, unknown>;
  headers?: Record<string, string>;
  responseType?: "json" | "blob";
}
export class ApiError extends Error {
  status: number;
  details: unknown;
  requestId: string | null;
}
export function configureApi(options: {
  organizationId: number | null;
  unauthorized: () => void;
  forbidden: () => void;
}): void;
export interface ApiClient {
  get<T = unknown>(endpoint: string, options?: RequestOptions): Promise<T>;
  post<T = unknown>(endpoint: string, data?: unknown, options?: RequestOptions): Promise<T>;
  put<T = unknown>(endpoint: string, data?: unknown, options?: RequestOptions): Promise<T>;
  patch<T = unknown>(endpoint: string, data?: unknown, options?: RequestOptions): Promise<T>;
  delete<T = unknown>(endpoint: string, options?: RequestOptions): Promise<T>;
}
export const api: ApiClient;
export default api;
