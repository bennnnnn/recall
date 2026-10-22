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

  constructor(status: number, body: string) {
    const read = readErrorBody(body);
    super(read.message || `Request failed: ${status}`);
    this.name = "ApiRequestError";
    this.status = status;
    this.code = read.code;
    this.detail = read.message;
    this.fields = read.fields;
  }
}
