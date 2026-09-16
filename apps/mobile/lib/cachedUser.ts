import {
  cacheDirectory,
  deleteAsync,
  getInfoAsync,
  readAsStringAsync,
  writeAsStringAsync,
} from "expo-file-system/legacy";

import type { User } from "@/lib/api/types";

// A previous user's started write must finish before signout clears it or a
// new account replaces it. Readers also wait to avoid observing partial files.
let pendingCacheWrite: Promise<void> = Promise.resolve();
function updateCache(write: () => Promise<void>): Promise<void> {
  const result = pendingCacheWrite.then(write).catch(() => {});
  pendingCacheWrite = result;
  return result;
}

const CACHED_USER_PATH = `${cacheDirectory ?? ""}cached-user.json`;

/**
 * The subset of ``User`` persisted to the filesystem cache.
 *
 * Only non-sensitive display fields are cached — enough to paint the app
 * instantly on cold start (name, avatar, plan for gating) without blocking
 * on an ``api.me()`` round trip. PII (email, age, country, job, location,
 * custom_instructions) and prefs (push/email reminder flags, reminder lead,
 * memory enabled, response style/tone, etc.) are deliberately NOT cached:
 * the cache directory can be read by a backup tool or another app with
 * filesystem access, so we keep it to fields that are already visible to
 * anyone who sees the app on the device. Everything else is re-fetched
 * from the API on launch.
 */
export type CachedUser = Pick<User, "id" | "name" | "avatar_url" | "plan">;

function decodeJwtClaims(token: string): Record<string, unknown> | null {
  try {
    const parts = token.split(".");
    if (parts.length !== 3 || parts.some((part) => !part)) return null;
    const payload = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const padded = payload.padEnd(Math.ceil(payload.length / 4) * 4, "=");
    const claims: unknown = JSON.parse(atob(padded));
    return typeof claims === "object" && claims !== null
      ? claims as Record<string, unknown>
      : null;
  } catch {
    return null;
  }
}

/** Decode only to select cached display fields, never to authenticate or grant
 * access. A cache from a previous account can survive a failed file deletion. */
export function cachedUserMatchesToken(cached: CachedUser, token: string): boolean {
  const claims = decodeJwtClaims(token);
  return claims !== null && typeof claims.sub === "string" && claims.sub === cached.id;
}

/**
 * Client-side expiry is only a latency hint: the server still authenticates
 * every request. Refresh slightly before expiry so cold-start providers do not
 * all send one doomed request and then replay after the shared 401 refresh.
 * Opaque/unreadable tokens keep the old behavior instead of being rejected.
 */
export function accessTokenNeedsRefresh(
  token: string,
  nowMs: number = Date.now(),
  skewSeconds = 30,
): boolean {
  const claims = decodeJwtClaims(token);
  const exp = claims?.exp;
  if (typeof exp !== "number" || !Number.isFinite(exp)) return false;
  return exp * 1000 <= nowMs + Math.max(0, skewSeconds) * 1000;
}

/** Default values for the fields NOT in ``CachedUser`` — used to construct a
 * full ``User`` from a cached subset so the in-memory state stays typed as
 * ``User`` (callers don't need to handle a partial). These defaults are
 * replaced by the real values within a second or two of cold start, once
 * ``api.me()`` returns. */
const DEFAULT_USER_FIELDS: Omit<User, keyof CachedUser> = {
  email: "",
  default_model: "",
  enabled_models: null,
  response_style: "",
  response_tone: "",
  memory_enabled: false,
  push_notifications_enabled: false,
  email_reminders_enabled: false,
  reminder_lead_minutes: 0,
  locale: "",
  timezone: "",
  location: null,
  location_enabled: false,
  custom_instructions: null,
  age: null,
  country: null,
  job: null,
  created_at: "",
  sign_in_provider: undefined,
  quiet_hours_enabled: false,
  quiet_hours_start_minute: 1320,
  quiet_hours_end_minute: 420,
};

/** Construct a full ``User`` from a cached subset + safe defaults for the
 * re-fetched fields. The result is replaced by the real ``api.me()`` response
 * within a second or two of cold start. */
export function mergeCachedUser(cached: CachedUser): User {
  // M4: never trust a cached plan — default to "free" so a lapsed Pro
  // subscription doesn't flash Pro UI (upgrade sheet hidden, wrong quota
  // copy) before /auth/me confirms. The server upgrades after the
  // background fetch lands.
  return { ...DEFAULT_USER_FIELDS, ...cached, plan: "free" };
}

/** Last-known user display fields, used to paint the app instantly on cold
 * start instead of blocking the whole navigator behind an api.me() round trip.
 * Best-effort — the cache directory can be purged by the OS at any time, in
 * which case cold start just falls back to the normal loading state. */
export async function readCachedUser(): Promise<CachedUser | null> {
  if (!cacheDirectory) return null;
  await pendingCacheWrite;
  try {
    const info = await getInfoAsync(CACHED_USER_PATH);
    if (!info.exists) return null;
    const raw = await readAsStringAsync(CACHED_USER_PATH);
    const parsed = JSON.parse(raw) as Partial<CachedUser>;
    if (!parsed || typeof parsed.id !== "string") return null;
    return {
      id: parsed.id,
      name: parsed.name ?? null,
      avatar_url: parsed.avatar_url ?? null,
      plan: parsed.plan === "pro" ? "pro" : "free",
    };
  } catch {
    return null;
  }
}

/** Persist only the non-sensitive display fields to the filesystem cache.
 *
 * PII (email, age, country, job, location, custom_instructions) and prefs
 * (push/email flags, reminder lead, memory enabled, response style/tone)
 * are stripped — the cache directory can be read by a backup tool or another
 * app, so we keep it to fields already visible on the device. Everything
 * else is re-fetched from the API on launch. */
export async function writeCachedUser(user: User): Promise<void> {
  if (!cacheDirectory) return;
  try {
    const cached: CachedUser = {
      id: user.id,
      name: user.name,
      avatar_url: user.avatar_url,
      plan: user.plan,
    };
    await updateCache(() => writeAsStringAsync(CACHED_USER_PATH, JSON.stringify(cached)));
  } catch {
    /* best-effort */
  }
}

export async function clearCachedUser(): Promise<void> {
  if (!cacheDirectory) return;
  try {
    await updateCache(() => deleteAsync(CACHED_USER_PATH, { idempotent: true }));
  } catch {
    /* ignore */
  }
}
