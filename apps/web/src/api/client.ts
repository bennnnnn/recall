import type { AuthResult } from "@/api/types";

const API_URL =
  (import.meta.env.VITE_API_URL as string | undefined) ?? "http://localhost:8000";

export function apiUrl(path: string): string {
  return `${API_URL}${path}`;
}

export class ApiRequestError extends Error {
  readonly status: number;
  constructor(status: number, body: string) {
    super(body || `Request failed: ${status}`);
    this.name = "ApiRequestError";
    this.status = status;
  }
}

const AUTH_TIMEOUT_MS = 15_000;

async function fetchWithTimeout(
  url: string,
  init: RequestInit,
  timeoutMs = AUTH_TIMEOUT_MS,
): Promise<Response> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      throw new Error("Could not reach the Recall API. Is it running?");
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

// Token storage — tab-scoped (sessionStorage). A refresh-token cookie + CSRF
// is a later slice; for now access + refresh live in sessionStorage so a new
// tab starts logged out, matching a personal app on a shared machine.
const ACCESS_KEY = "recall.access_token";
const REFRESH_KEY = "recall.refresh_token";

export function getAccessToken(): string | null {
  return sessionStorage.getItem(ACCESS_KEY);
}
export function getRefreshToken(): string | null {
  return sessionStorage.getItem(REFRESH_KEY);
}
export function setTokenPair(access: string, refresh: string): void {
  sessionStorage.setItem(ACCESS_KEY, access);
  sessionStorage.setItem(REFRESH_KEY, refresh);
}
export function clearTokens(): void {
  sessionStorage.removeItem(ACCESS_KEY);
  sessionStorage.removeItem(REFRESH_KEY);
}

let refreshInFlight: Promise<string | null> | null = null;

export async function refreshAccessToken(): Promise<string | null> {
  if (refreshInFlight) return refreshInFlight;
  refreshInFlight = (async () => {
    try {
      const refreshToken = getRefreshToken();
      if (!refreshToken) return null;
      const response = await fetchWithTimeout(apiUrl("/auth/refresh"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
      if (!response.ok) return null;
      const data = (await response.json()) as AuthResult;
      setTokenPair(data.access_token, data.refresh_token);
      return data.access_token;
    } catch {
      return null;
    } finally {
      refreshInFlight = null;
    }
  })();
  return refreshInFlight;
}

// Authed JSON request with 401 -> refresh -> retry.
export async function request<T>(
  path: string,
  token: string,
  init?: RequestInit,
  allowRefresh = true,
  timeoutMs = 30_000,
): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  const externalSignal = init?.signal ?? null;
  const onExternalAbort = () => controller.abort();
  externalSignal?.addEventListener("abort", onExternalAbort);
  try {
    const response = await fetch(apiUrl(path), {
      ...init,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
        ...(init?.headers ?? {}),
      },
    });
    if (response.status === 401 && allowRefresh) {
      const refreshed = await refreshAccessToken();
      if (refreshed) return request<T>(path, refreshed, init, false);
      clearTokens();
      const text = await response.text();
      throw new ApiRequestError(response.status, text);
    }
    if (!response.ok) {
      const text = await response.text();
      throw new ApiRequestError(response.status, text);
    }
    if (response.status === 204) return undefined as T;
    return response.json() as Promise<T>;
  } finally {
    externalSignal?.removeEventListener("abort", onExternalAbort);
    clearTimeout(timeout);
  }
}

// Authed fetch returning the raw Response (for SSE streaming). Same 401 ->
// refresh -> retry as request().
export async function requestRaw(
  path: string,
  token: string,
  init: RequestInit,
  allowRefresh = true,
  timeoutMs = 30_000,
): Promise<Response> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  const externalSignal = init.signal ?? null;
  const onExternalAbort = () => controller.abort();
  externalSignal?.addEventListener("abort", onExternalAbort);
  try {
    const response = await fetch(apiUrl(path), {
      ...init,
      signal: controller.signal,
      headers: {
        Authorization: `Bearer ${token}`,
        ...init.headers,
      },
    });
    if (response.status === 401 && allowRefresh) {
      const refreshed = await refreshAccessToken();
      if (refreshed) {
        return requestRaw(path, refreshed, init, false);
      }
      clearTokens();
    }
    return response;
  } finally {
    externalSignal?.removeEventListener("abort", onExternalAbort);
    clearTimeout(timeout);
  }
}

export { fetchWithTimeout };
