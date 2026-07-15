import { getApiUrl } from "@/lib/config";
import { getRefreshToken, setTokenPair } from "@/lib/auth";

import type { AuthResult } from "@/lib/api/types";

let onUnauthorized: (() => void) | null = null;
let onTokenRefresh: ((accessToken: string) => void) | null = null;

export function setUnauthorizedHandler(fn: (() => void) | null): void {
  onUnauthorized = fn;
}

/** Invoke the global unauthorized handler (e.g. SSE refresh failure). */
export function notifyUnauthorized(): void {
  onUnauthorized?.();
}

export function setTokenRefreshHandler(fn: ((accessToken: string) => void) | null): void {
  onTokenRefresh = fn;
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

let refreshInFlight: Promise<string | null> | null = null;

/** Refresh the access token using the stored refresh token. Returns the new
 * access token, or null if refresh failed (caller should surface an auth
 * error). Single-flighted so concurrent callers share one refresh. Exported
 * so the SSE/WS streaming paths can mirror the REST `request()` 401→refresh
 * behaviour (they use raw fetch/WebSocket and otherwise can't auto-refresh). */
export async function refreshAccessToken(): Promise<string | null> {
  if (refreshInFlight) return refreshInFlight;
  refreshInFlight = (async () => {
    try {
      const refreshToken = await getRefreshToken();
      if (!refreshToken) return null;
      const response = await fetchWithTimeout(apiUrl("/auth/refresh"), {
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

/**
 * Authed fetch that returns the raw ``Response`` (for callers that need the
 * body as a stream, non-JSON, or binary). Mirrors ``request()``'s 401→refresh
 * →retry behaviour so non-JSON endpoints (SSE, file downloads, link preview)
 * get the same auto-refresh as REST. The caller controls Content-Type /
 * Accept / body via ``init``; only Authorization (when ``token`` is non-empty)
 * is added.
 *
 * This is the single network-boundary helper for non-JSON fetches — every
 * HTTP egress from the mobile app should go through ``request``,
 * ``requestRaw``, ``requestSse``, or ``fetchExportText`` (all in lib/api),
 * never a bare ``fetch(getApiUrl()...)``. ``file://`` reads remain the only
 * exception (expo-file-system, not network).
 */
export async function requestRaw(
  path: string,
  token: string | null,
  init?: RequestInit,
  allowRefresh = true,
  timeoutMs = 30_000,
): Promise<Response> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  const externalSignal = init?.signal ?? null;
  const onExternalAbort = () => controller.abort();
  externalSignal?.addEventListener("abort", onExternalAbort);

  try {
    const callerHeaders = (init?.headers ?? {}) as Record<string, string>;
    const headers: Record<string, string> = { ...callerHeaders };
    if (token) headers.Authorization = `Bearer ${token}`;

    const response = await fetch(apiUrl(path), {
      ...init,
      signal: controller.signal,
      headers,
    });

    if (response.status === 401 && allowRefresh && token) {
      const refreshed = await refreshAccessToken();
      if (refreshed) {
        return requestRaw(path, refreshed, init, false);
      }
      onUnauthorized?.();
    }
    return response;
  } finally {
    externalSignal?.removeEventListener("abort", onExternalAbort);
    clearTimeout(timeout);
  }
}

/**
 * Authed fetch for an SSE chat stream. Returns the raw ``Response`` so the
 * caller can read ``response.body`` as a stream of events. Handles 401→refresh
 * →retry so a backgrounded-then-resumed app doesn't fail the stream silently.
 *
 * This is the SSE counterpart to ``request()`` — the streaming paths (chat
 * send / regenerate / edit) must go through it (or the WS equivalent) so the
 * lib/api boundary stays the single network egress point.
 */
export async function requestSse(
  path: string,
  token: string,
  body: Record<string, unknown>,
  signal?: AbortSignal,
  allowRefresh = true,
): Promise<Response> {
  return requestRaw(
    path,
    token,
    {
      method: "POST",
      signal,
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      },
      body: JSON.stringify(body),
    },
    allowRefresh,
  );
}
