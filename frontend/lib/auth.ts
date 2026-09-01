const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
export type User = { id: string; name: string; email: string; plan: "FREE" | "PREMIUM"; created_at: string };
export type AuthResult = { access_token: string; token_type: "bearer"; user: User };

export async function request<T>(path: string, init: RequestInit = {}, token?: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { ...init, headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...init.headers } });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || "Something went wrong. Please try again.");
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

export function saveSession(result: AuthResult) { localStorage.setItem("access_token", result.access_token); }
export function getToken() { return typeof window === "undefined" ? null : localStorage.getItem("access_token"); }

export async function authedRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  if (!token) throw new Error("Your session has expired. Please sign in again.");
  return request<T>(path, init, token);
}
