const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export type Plan = "FREE" | "PREMIUM";
export type User = { id: string; name: string; email: string; plan: Plan; created_at: string };
export type AuthResult = { access_token: string; token_type: "bearer"; user: User };

/** Carries the HTTP status so callers can tell "needs Premium" from "failed". */
export class ApiRequestError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code?: string,
  ) {
    super(message);
    this.name = "ApiRequestError";
  }
}

export async function request<T>(path: string, init: RequestInit = {}, token?: string): Promise<T> {
  const isFormData = typeof FormData !== "undefined" && init.body instanceof FormData;
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiRequestError(
      body.detail || body.error?.message || "Something went wrong. Please try again.",
      response.status,
      body.error?.code,
    );
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

export function saveSession(result: AuthResult) {
  localStorage.setItem("access_token", result.access_token);
}

export function getToken() {
  return typeof window === "undefined" ? null : localStorage.getItem("access_token");
}

export function clearSession() {
  localStorage.removeItem("access_token");
}

export async function authedRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  if (!token) throw new ApiRequestError("Your session has expired. Please sign in again.", 401);
  return request<T>(path, init, token);
}

export const getCurrentUser = () => authedRequest<User>("/auth/me");

/** True when a request failed only because the account is on the FREE plan. */
export const isPlanError = (error: unknown) => error instanceof ApiRequestError && error.status === 403;
