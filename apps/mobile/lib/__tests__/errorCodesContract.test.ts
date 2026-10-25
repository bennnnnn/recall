/**
 * The phone's half of docs/fixtures/error_codes.json (code-health audit DUP-10). The API
 * test writes each refusal from a real request; here each reaches its reader by `code`,
 * so rewording the server's English changes nothing the phone does.
 */
import fixture from "../../../../docs/fixtures/error_codes.json";
import { AttachmentError, presignFailure } from "@/features/attachments/model/attachmentErrors";
import { accountExistsProvider } from "@/features/auth/model/accountExists";
import { signInRefusalKey } from "@/features/auth/model/signInRefusal";
import { ApiRequestError } from "@/lib/api/client";
import { CONSENT_REQUIRED_CODE } from "@/lib/api/consentRefusal";
import { scanFailureMessage } from "@/lib/scanner/scanReadError";
import { refusalCode, resolveChatError } from "@/features/chat/model/errorMessage";
import { memoryFailure, memoryFailureKey } from "@/features/memory/model/memoryFailure";
import { liveTalkErrorGate } from "@/features/speech/model/liveTalkLogic";
import { voiceRefusalKey } from "@/features/speech/model/voiceRefusal";

jest.mock("@/lib/config", () => ({ getApiUrl: () => "http://test.local" }));
jest.mock("@/lib/auth", () => ({
  getSessionGeneration: () => 0,
  requireTokenSession: jest.fn(),
  SessionChangedError: class extends Error {},
  getRefreshToken: jest.fn(),
  setTokenPair: jest.fn(),
}));

type Refusal = { status: number; detail: unknown };
const refusals = fixture as Record<string, Refusal>;
const t = (key: string) => key;

function refused(name: string): ApiRequestError {
  const refusal = refusals[name];
  if (!refusal) throw new Error(`no ${name} in docs/fixtures/error_codes.json`);
  return new ApiRequestError(refusal.status, JSON.stringify({ detail: refusal.detail }));
}

it("reads every refusal's code and words from its body once", () => {
  for (const [name, refusal] of Object.entries(refusals)) {
    const error = refused(name);
    expect(error.message).not.toBe("");
    if (refusal.status !== 422) expect(error.code).toBe((refusal.detail as { code: string }).code);
  }
});

it("opens the consent screen on consent_required", () => {
  expect(refused("consent_required").code).toBe(CONSENT_REQUIRED_CODE);
});

it("offers the earlier way to sign in", () => {
  expect(accountExistsProvider(refused("account_exists"))).toBe("apple");
});

it.each([
  ["sign_in_rate_limited", "login.error_rate_limited"],
  ["sign_in_unavailable", "login.error_unavailable"],
  // Dev login passes the request limiter: Redis down there is the API's own outage body.
  ["service_unavailable", "login.error_unavailable"],
  ["google_unavailable", "login.error_unavailable"],
  ["apple_unavailable", "login.error_unavailable"],
  ["google_token_invalid", "login.error_token_invalid"],
  ["apple_token_invalid", "login.error_token_invalid"],
  ["apple_key_unknown", "login.error_token_invalid"],
  ["google_email_unverified", "login.error_google_email_unverified"],
  ["apple_email_unverified", "login.error_apple_email_unverified"],
  ["google_email_missing", "login.error_google_email_missing"],
  ["apple_email_missing", "login.error_apple_email_missing"],
  ["apple_not_configured", "login.error_apple_not_configured"],
  ["dev_auth_disabled", "login.error_dev_disabled"],
])("words a refused sign-in: %s", (name, key) => {
  expect(signInRefusalKey(refused(name))).toBe(key);
});

it.each([
  ["scan_not_available", "chat.scan_unavailable"],
  ["scan_too_large", "chat.scan_too_large"],
  ["scan_rate_limited", "chat.scan_rate_limit"],
  ["scan_spend_cap", "chat.scan_spend_cap"],
  ["scan_invalid_image", null],
  // A Redis outage said "Too many scans in a row", then "couldn't scan that photo".
  ["service_unavailable", "common.service_unavailable"],
])("words a refused scan: %s", (name, words) => {
  expect(scanFailureMessage(refused(name), t)).toBe(words);
});

it.each([
  ["presign_unsupported_type", "unsupported_type"],
  ["presign_too_large", "too_large"],
  ["presign_daily_limit", "daily_limit"],
])("names a refused upload: %s", (name, reason) => {
  const failure = presignFailure(refused(name));
  expect(failure).toBeInstanceOf(AttachmentError);
  expect((failure as AttachmentError).reason).toBe(reason);
});

it.each([
  ["image_daily_limit", false, "quota", "chat.image_daily_limit_free"],
  ["image_daily_limit", true, "notice", "chat.image_daily_limit_paid"],
  ["image_content_blocked", false, "notice", "chat.image_content_blocked"],
])("words a refused picture: %s (paid %s)", (name, isPaid, kind, words) => {
  const error = refused(name);
  const code = refusalCode(error.code ?? undefined, error.fields.feature);
  expect(resolveChatError({ message: error.message, code, isPaid, t })).toEqual({ kind, message: words });
});

it.each([
  ["dictation_daily_limit", "chat.voice_daily_limit"],
  ["dictation_rate_limited", "chat.voice_rate_limited"],
  ["service_unavailable", "common.service_unavailable"],
])("words a refused dictation: %s", (name, words) => {
  expect(voiceRefusalKey(refused(name))).toBe(words);
});

// Every 503 said "Live talk isn't set up on this server yet", a Redis outage included.
it.each([
  ["service_unavailable", "outage"],
  ["live_talk_not_configured", "unconfigured"],
])("gates live talk on a refused 503: %s", (name, gate) => {
  expect(liveTalkErrorGate(refused(name))).toBe(gate);
});

it.each([
  ["service_unavailable", "unavailable", "common.service_unavailable"],
  // Paused by the spend cap is no outage: the action's own "couldn't" line, as before.
  ["memory_spend_cap", "failed", "memory.edit_failed"],
])("words a refused memory edit: %s", (name, failure, words) => {
  expect(memoryFailure(refused(name))).toBe(failure);
  expect(memoryFailureKey(memoryFailure(refused(name)), "memory.edit_failed")).toBe(words);
});

it("words a chat turn the API could not serve", () => {
  const error = refused("service_unavailable");
  expect(resolveChatError({ message: error.message, code: error.code ?? undefined, isPaid: false, t }))
    .toEqual({ kind: "generic", message: "common.service_unavailable" });
});
