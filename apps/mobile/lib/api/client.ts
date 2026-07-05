import { getApiUrl } from "@/lib/config";
import { getRefreshToken, setTokenPair } from "@/lib/auth";

import type { AuthResult } from "@/lib/api/types";

let onUnauthorized: (() => void) | null = null;
let onTokenRefresh: ((accessToken: string) => void) | null = null;

export function setUnauthorizedHandler(fn: (() => void) | null): void {
  onUnauthorized = fn;
}

export function setTokenRefreshHandler(fn: ((accessToken: string) => void) | null): void {
  onTokenRefresh = fn;
}

let refreshInFlight: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  if (refreshInFlight) return refreshInFlight;
  refreshInFlight = (async () => {
    try {
      const refreshToken = await getRefreshToken();
      if (!refreshToken) return null;
      const response = await fetch(apiUrl("/auth/refresh"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
      if (!response.ok) return null;
      const data = (await response.json()) as AuthResult;
      await setTokenPair(data.access_token, data.refresh_token);
      onTokenRefresh?.(data.access_token);
      return data.access_token;
    } catch {
      return null;
    } finally {
      // Every exit path (including the no-refresh-token early return) must
      // clear this, or a single missing-refresh-token 401 permanently wedges
      // refreshAccessToken to always short-circuit to this stale resolved
      // promise for the rest of the app session.
      refreshInFlight = null;
    }
  })();
  return refreshInFlight;
}

export async function logoutSession(token: string, refreshToken: string | null): Promise<void> {
  try {
    await fetch(apiUrl("/auth/logout"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
  } catch {
    /* best-effort */
  }
}

export function apiUrl(path: string) {
  return `${getApiUrl()}${path}`;
}

const AUTH_FETCH_TIMEOUT_MS = 15_000;

export async function fetchWithTimeout(url: string, init: RequestInit): Promise<Response> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), AUTH_FETCH_TIMEOUT_MS);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      throw new Error(
        "Could not reach the Recall server. Check Wi‑Fi (same network as your Mac) or USB debugging with the API running.",
      );
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

export async function request<T>(
  path: string,
  token: string,
  init?: RequestInit,
  allowRefresh = true,
): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 30_000);
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
      if (refreshed) {
        return request<T>(path, refreshed, init, false);
      }
      onUnauthorized?.();
      const text = await response.text();
      throw new Error(text || `Request failed: ${response.status}`);
    }

    if (!response.ok) {
      if (response.status === 401) {
        onUnauthorized?.();
      }
      const text = await response.text();
      throw new Error(text || `Request failed: ${response.status}`);
    }

    if (response.status === 204) {
      return undefined as T;
    }

    return response.json() as Promise<T>;
  } finally {
    externalSignal?.removeEventListener("abort", onExternalAbort);
    clearTimeout(timeout);
  }
}

export async function fetchExportText(token: string, allowRefresh = true): Promise<string> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 120_000);

  try {
    const response = await fetch(apiUrl("/auth/me/export"), {
      signal: controller.signal,
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${token}`,
      },
    });

    if (response.status === 401 && allowRefresh) {
      const refreshed = await refreshAccessToken();
      if (refreshed) {
        return fetchExportText(refreshed, false);
      }
      onUnauthorized?.();
      const text = await response.text();
      throw new Error(text || `Request failed: ${response.status}`);
    }

    if (!response.ok) {
      if (response.status === 401) {
        onUnauthorized?.();
      }
      const text = await response.text();
      throw new Error(text || `Request failed: ${response.status}`);
    }

    return response.text();
  } finally {
    clearTimeout(timeout);
  }
}
