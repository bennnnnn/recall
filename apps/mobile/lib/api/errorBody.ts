/**
 * A refused request's body, read once (code-health audit DUP-10). No imports: tests that
 * stub the network client keep the real error.
 */

/** A refusal's body, read once: `{"detail": {"code", "message", ...}}`, a plain
 * `{"detail": "…"}`, FastAPI's validation list, or text that is not JSON. */
type ErrorBody = {
  /** What a reader switches on; null for a body that names none. */
  code: string | null;
  /** The English to show. */
  message: string;
  /** Anything else the refusal carries (`sign_in_with`; FastAPI's validation `errors`). */
  fields: Readonly<Record<string, unknown>>;
};

export function readErrorBody(body: string): ErrorBody {
  const text = body.trim();
  let detail: unknown;
  try {
    detail = (JSON.parse(text) as { detail?: unknown } | null)?.detail;
  } catch {
    return { code: null, message: text, fields: {} };
  }
  if (typeof detail === "string") return { code: null, message: detail.trim(), fields: {} };
  if (Array.isArray(detail)) {
    const messages = detail.map((item) =>
      typeof item === "string" ? item : String((item as { msg?: unknown } | null)?.msg ?? ""),
    );
    return { code: null, message: messages.filter(Boolean).join(", "), fields: { errors: detail } };
  }
  if (detail && typeof detail === "object") {
    const { code, message, ...fields } = detail as Record<string, unknown>;
    return {
      code: typeof code === "string" ? code : null,
      message: typeof message === "string" ? message : "",
      fields,
    };
  }
  return { code: null, message: text, fields: {} };
}

/**
 * A refused request. The body is read once here (code-health audit DUP-10): readers
 * switch on `code` and show `message`, never parse the body or match its English.
 */
export class ApiRequestError extends Error {
  readonly status: number;
  readonly code: string | null;
  /** The server's words; empty when the body carried none (`message` then says the status). */
  readonly detail: string;
  readonly fields: Readonly<Record<string, unknown>>;
  /** How long the server asked to be left alone (its `Retry-After`), or null. */
  readonly retryAfterMs: number | null;

  constructor(status: number, body: string, retryAfterMs: number | null = null) {
    const read = readErrorBody(body);
    super(read.message || `Request failed: ${status}`);
    this.name = "ApiRequestError";
    this.status = status;
    this.code = read.code;
    this.detail = read.message;
    this.fields = read.fields;
    this.retryAfterMs = retryAfterMs;
  }
}

/** The longest wait a `Retry-After` is taken at: a wrong header must not stall the app. */
const MAX_RETRY_AFTER_MS = 5 * 60_000;

/** A `Retry-After` (seconds, or an HTTP date) in ms, at most five minutes; null without one. */
export function readRetryAfter(value: string | null | undefined, now = Date.now()): number | null {
  const text = value?.trim();
  if (!text) return null;
  const ms = /^\d+$/.test(text) ? Number(text) * 1000 : Date.parse(text) - now;
  return Number.isFinite(ms) ? Math.min(Math.max(ms, 0), MAX_RETRY_AFTER_MS) : null;
}
