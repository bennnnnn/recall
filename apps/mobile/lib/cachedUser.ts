import type { User } from "@/lib/api/types";
import { cacheFile } from "@/lib/cache/cacheFile";
import { planOf } from "@/lib/plan";
import { tokenSubject } from "@/lib/tokenSubject";

const cachedUserFile = cacheFile("cached-user.json");

/** The file's shape. A file without it (written before the settings were kept) is not
 * painted: its settings would be placeholders, so the launch waits for /auth/me once. */
const CACHE_VERSION = 2;

/** The display fields: enough to paint the app at once on a cold start. The AI-consent time
 * is kept too (not PII): without it every cold start would show the consent screen until
 * `api.me()` lands. */
type CachedDisplay = Pick<User, "id" | "name" | "avatar_url" | "ai_data_consent_at" | "locale">;

/**
 * The settings the phone acts on before `/auth/me` answers: the model a message names (Auto
 * or the chosen model), the plan (a Pro reply read aloud in the cloud voice, not the phone's),
 * memory, voices, emoji and tone. With placeholders in their place a send named Auto instead
 * of the user's model and a Pro user heard the phone's voice. None is personal: no email,
 * age, country, job, place or custom instructions, and no push, email or reminder switches
 * (the bootstrap sync acts on those only once the server has said, `profileValidated`). The
 * cache directory can be read by a backup tool, so anything personal stays out.
 */
const SETTING_FIELDS = [
  "plan",
  "features",
  "default_model",
  "enabled_models",
  "memory_enabled",
  "memory_include_sensitive",
  "emoji_use",
  "response_tone",
  "follow_up_suggestions_enabled",
  "web_search_enabled",
  "tts_voice",
  "reply_voice",
  "reply_voice_heard",
] as const satisfies readonly (keyof User)[];

type CachedSettings = Pick<User, (typeof SETTING_FIELDS)[number]>;

type CachedUser = CachedDisplay & CachedSettings;

/** Decode only to select cached display fields, never to authenticate or grant
 * access. A cache from a previous account can survive a failed file deletion. */
export function cachedUserMatchesToken(cached: Pick<User, "id">, token: string): boolean {
  return tokenSubject(token) === cached.id;
}

/** A cache written before the consent field existed leaves it out: undefined,
 * not null, so an offline cold start does not ask an account that already agreed. */
function cachedConsentAt(value: unknown): string | null | undefined {
  return typeof value === "string" || value === null ? value : undefined;
}

/** Default values for the fields NOT cached — used to construct a full ``User`` from the
 * cached subset so the in-memory state stays typed as ``User`` (callers don't need to handle
 * a partial). They are replaced by the real values within a second or two of cold start,
 * once ``api.me()`` returns; nothing acts on them before (`profileValidated`). */
const DEFAULT_USER_FIELDS: Omit<User, keyof CachedUser> = {
  email: "",
  push_notifications_enabled: false,
  email_reminders_enabled: false,
  reminder_lead_minutes: 0,
  timezone: "",
  location: null,
  location_enabled: null,
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

/** Construct a full ``User`` from the cached subset + safe defaults for the re-fetched
 * fields. The plan is the one the account last had: the server checks every request, and
 * `/auth/me` replaces it within a second or two of cold start. */
export function mergeCachedUser(cached: CachedUser): User {
  return { ...DEFAULT_USER_FIELDS, ...cached };
}

const isString = (value: unknown): value is string => typeof value === "string";
const isBool = (value: unknown): value is boolean => typeof value === "boolean";
const isStringList = (value: unknown): value is string[] => Array.isArray(value) && value.every(isString);

/** Each cached setting as it was written, or its "unset" value when it is not what it should be. */
function readSettings(parsed: Record<string, unknown>): CachedSettings {
  const optional = <T>(value: unknown, valid: (v: unknown) => v is T): T | undefined =>
    valid(value) ? value : undefined;
  const nullable = <T>(value: unknown, valid: (v: unknown) => v is T): T | null =>
    valid(value) ? value : null;
  return {
    plan: planOf({ plan: isString(parsed.plan) ? parsed.plan : null }),
    features: optional(parsed.features, isStringList) as CachedSettings["features"],
    default_model: isString(parsed.default_model) ? parsed.default_model : "",
    enabled_models: nullable(parsed.enabled_models, isStringList),
    memory_enabled: isBool(parsed.memory_enabled) ? parsed.memory_enabled : true,
    memory_include_sensitive: optional(parsed.memory_include_sensitive, isBool),
    emoji_use: optional(parsed.emoji_use, isString),
    response_tone: isString(parsed.response_tone) ? parsed.response_tone : "",
    follow_up_suggestions_enabled: optional(parsed.follow_up_suggestions_enabled, isBool),
    web_search_enabled: optional(parsed.web_search_enabled, isBool),
    tts_voice: nullable(parsed.tts_voice, isString) as CachedSettings["tts_voice"],
    reply_voice: nullable(parsed.reply_voice, isString),
    reply_voice_heard: nullable(parsed.reply_voice_heard, isString),
  };
}

/** Last-known user display fields and settings, used to paint the app instantly on cold
 * start instead of blocking the whole navigator behind an api.me() round trip.
 * Best-effort — the cache directory can be purged by the OS at any time, in
 * which case cold start just falls back to the normal loading state. */
export async function readCachedUser(): Promise<CachedUser | null> {
  const raw = await cachedUserFile.read();
  if (raw === null) return null;
  try {
    const parsed = JSON.parse(raw) as Record<string, unknown> | null;
    if (!parsed || typeof parsed.id !== "string" || parsed.v !== CACHE_VERSION) return null;
    return {
      id: parsed.id,
      name: isString(parsed.name) ? parsed.name : null,
      avatar_url: isString(parsed.avatar_url) ? parsed.avatar_url : null,
      ai_data_consent_at: cachedConsentAt(parsed.ai_data_consent_at),
      locale: isString(parsed.locale) ? parsed.locale : "",
      ...readSettings(parsed),
    };
  } catch {
    return null;
  }
}

/** The cached account's language, read before the first render so the first
 * frame is drawn in it (`lib/launchPrefs.ts`); null without one. */
export function readCachedLocaleSync(): string | null {
  const raw = cachedUserFile.readSync();
  if (raw === null) return null;
  try {
    const parsed = JSON.parse(raw) as { locale?: unknown } | null;
    const locale = parsed?.locale;
    return typeof locale === "string" && locale.trim() ? locale.trim() : null;
  } catch {
    return null;
  }
}

/** Persist only the display fields and the settings above to the filesystem cache:
 * PII (email, age, country, job, location, custom_instructions) and the push, email and
 * reminder switches are stripped, and re-fetched from the API on launch. */
export function writeCachedUser(user: User): Promise<void> {
  const settings: Record<string, unknown> = {};
  for (const field of SETTING_FIELDS) {
    if (user[field] !== undefined) settings[field] = user[field];
  }
  const cached = {
    v: CACHE_VERSION,
    id: user.id,
    name: user.name,
    avatar_url: user.avatar_url,
    ai_data_consent_at: user.ai_data_consent_at,
    locale: user.locale,
    ...settings,
  };
  return cachedUserFile.write(JSON.stringify(cached));
}

export function clearCachedUser(): Promise<void> {
  return cachedUserFile.clear();
}
