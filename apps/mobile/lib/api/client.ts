import { getApiUrl } from "@/lib/config";
import {
  getRefreshToken,
  getSessionGeneration,
  requireTokenSession,
  SessionChangedError,
  setTokenPair,
} from "@/lib/auth";

import type { AuthResult, User } from "@/lib/api/types";

let onUnauthorized: (() => void) | null = null;
let onTokenRefresh: ((accessToken: string, user?: User) => void) | null = null;

export function setUnauthorizedHandler(fn: (() => void) | null): void {
  onUnauthorized = fn;
}

export function notifyUnauthorized(generation = getSessionGeneration()): void {
  if (generation === getSessionGeneration()) onUnauthorized?.();
}

export function setTokenRefreshHandler(
  fn: ((accessToken: string, user?: User) => void) | null,
): void {
  onTokenRefresh = fn;
}

function requireSession(generation: number): void {
  if (generation !== getSessionGeneration()) throw new SessionChangedError();
}

function requireNotAborted(signal?: AbortSignal | null): void {
  if (!signal?.aborted) return;
  const error = new Error("Request canceled");
  error.name = "AbortError";
  throw error;
}

const AUTH_FETCH_TIMEOUT_MS = 15_000;

export async function fetchWithTimeout(url: string, init: RequestInit): Promise<Response> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), AUTH_FETCH_TIMEOUT_MS);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      throw new Error("Could not reach the Recall server. Check your connection and try again.");
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

let refreshInFlight: { generation: number; promise: Promise<string | null> } | null = null;

/** Share refresh within one session. Only an absent/rejected refresh credential
 * returns null; outages and secure storage failures must not sign the user out. */
export async function refreshAccessToken(): Promise<string | null> {
  const generation = getSessionGeneration();
  if (refreshInFlight?.generation === generation) return refreshInFlight.promise;
  const promise = (async () => {
    const refreshToken = await getRefreshToken();
    requireSession(generation);
    if (!refreshToken) return null;
    const response = await fetchWithTimeout(apiUrl("/auth/refresh"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    requireSession(generation);
    if (response.status === 401) return null;
    if (!response.ok) throw new ApiRequestError(response.status, await response.text());
    const data = (await response.json()) as AuthResult;
    requireSession(generation);
    if (!data || typeof data.access_token !== "string" || !data.access_token ||
      typeof data.refresh_token !== "string" || !data.refresh_token) {
      throw new Error("Recall returned an invalid sign-in response. Please try again.");
    }
    const saved = await setTokenPair(data.access_token, data.refresh_token, generation);
    requireSession(generation);
    if (!saved) throw new SessionChangedError();
    onTokenRefresh?.(data.access_token, data.user);
    return data.access_token;
  })();
  refreshInFlight = { generation, promise };
  try {
    return await promise;
  } finally {
    // An old account's completion must not release a newer account's refresh.
    if (refreshInFlight?.promise === promise) refreshInFlight = null;
  }
}

export async function logoutSession(token: string, refreshToken: string | null): Promise<void> {
  try {
    await fetchWithTimeout(apiUrl("/auth/logout"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
  } catch {
    /* Server revocation is best-effort; local credential removal is independent. */
  }
}

export class ApiRequestError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message || `Request failed: ${status}`);
    this.name = "ApiRequestError";
    this.status = status;
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
  const generation = getSessionGeneration();
  const response = await requestRaw(path, token, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  }, allowRefresh, timeoutMs);
  if (!response.ok) throw new ApiRequestError(response.status, await response.text());
  const data = response.status === 204 ? undefined : await response.json();
  requireSession(generation);
  return data as T;
}

export async function fetchExportText(token: string, allowRefresh = true): Promise<string> {
  const generation = getSessionGeneration();
  const response = await requestRaw("/auth/me/export", token, {
    headers: { Accept: "application/json" },
  }, allowRefresh, 120_000);
  if (!response.ok) throw new ApiRequestError(response.status, await response.text());
  const text = await response.text();
  requireSession(generation);
  return text;
}

/** Single authenticated fetch boundary for JSON, downloads, and SSE. Raw
 * responses keep their bodies unread; auth recovery always happens here. */
export async function requestRaw(
  path: string,
  token: string | null,
  init?: RequestInit,
  allowRefresh = true,
  timeoutMs = 30_000,
  retainStreamAbort = false,
): Promise<Response> {
  if (token) requireTokenSession(token);
  const generation = getSessionGeneration();
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  const externalSignal = init?.signal ?? null;
  const onExternalAbort = () => controller.abort();
  externalSignal?.addEventListener("abort", onExternalAbort, { once: true });
  let streamingBodyReturned = false;
  try {
    requireNotAborted(externalSignal);
    const headers = { ...(init?.headers ?? {}) } as Record<string, string>;
    if (token) headers.Authorization = `Bearer ${token}`;
    const response = await fetch(apiUrl(path), {
      ...init,
      signal: controller.signal,
      headers,
    });
    requireSession(generation);
    requireNotAborted(controller.signal);
    if (response.status === 401 && token) {
      if (allowRefresh) {
        const refreshed = await refreshAccessToken();
        requireSession(generation);
        requireNotAborted(controller.signal);
        if (refreshed) return requestRaw(path, refreshed, init, false, timeoutMs, retainStreamAbort);
      }
      notifyUnauthorized(generation);
    }
    streamingBodyReturned = retainStreamAbort && response.ok && response.body != null;
    return response;
  } finally {
    // SSE callers own one AbortController per stream. Keep forwarding Stop
    // after headers; the once-listener is released on abort or with that signal.
    if (!streamingBodyReturned) externalSignal?.removeEventListener("abort", onExternalAbort);
    clearTimeout(timeout);
  }
}

/** Streaming counterpart to request; returns the raw event-stream response. */
export async function requestSse(
  path: string,
  token: string,
  body: Record<string, unknown>,
  signal?: AbortSignal,
  allowRefresh = true,
  timeoutMs = 30_000,
): Promise<Response> {
  return requestRaw(path, token, {
    method: "POST",
    signal,
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(body),
  }, allowRefresh, timeoutMs, true);
}
