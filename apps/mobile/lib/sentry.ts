/**
 * Optional Sentry: a no-op when EXPO_PUBLIC_SENTRY_DSN is unset. Same rule as
 * the API's (apps/api/app/core/sentry.py): an event carries what broke, never
 * what the user wrote, what the model answered, a request body or a token.
 */

import * as Sentry from "@sentry/react-native";
import type { Breadcrumb, ErrorEvent } from "@sentry/react-native";

let initialized = false;

const SENSITIVE_HEADERS = new Set([
  "authorization",
  "cookie",
  "set-cookie",
  "x-api-key",
  "x-forwarded-authorization",
]);

// Bearer tokens, JWTs (our access tokens), Live Talk's ek_ secret, provider keys.
const SECRET_PATTERNS: readonly RegExp[] = [
  /\bBearer\s+[A-Za-z0-9._~+/=-]+/gi,
  /\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+/g,
  /\b(?:ek|sk|rk)_[A-Za-z0-9_-]{8,}/g,
];

/** Errors can quote what they choked on; keep the start, which says what broke. */
const MAX_ERROR_TEXT = 300;

export function redactSecrets(text: string): string {
  let out = text;
  for (const pattern of SECRET_PATTERNS) out = out.replace(pattern, "[REDACTED]");
  return out.length > MAX_ERROR_TEXT ? `${out.slice(0, MAX_ERROR_TEXT)}…` : out;
}

function withoutQuery(url: unknown): unknown {
  return typeof url === "string" ? url.split(/[?#]/, 1)[0] : url;
}

/** Console lines can hold chat text; network crumbs keep only method, path and status. */
export function scrubBreadcrumb(breadcrumb: Breadcrumb): Breadcrumb | null {
  if (breadcrumb.category === "console") return null;
  const data = breadcrumb.data;
  if (!data) return breadcrumb;
  const kept: Record<string, unknown> = {};
  for (const key of ["method", "status_code", "url", "from", "to"]) {
    if (key in data) kept[key] = key === "url" ? withoutQuery(data[key]) : data[key];
  }
  return { ...breadcrumb, data: kept };
}

/** Drop bodies, query strings, cookies, auth headers, extras and user fields. */
export function scrubSentryEvent(event: ErrorEvent): ErrorEvent | null {
  const request = event.request;
  if (request) {
    delete request.data;
    delete request.cookies;
    request.query_string = undefined;
    request.url = withoutQuery(request.url) as string | undefined;
    for (const name of Object.keys(request.headers ?? {})) {
      if (SENSITIVE_HEADERS.has(name.toLowerCase()) && request.headers) {
        request.headers[name] = "[REDACTED]";
      }
    }
  }
  delete event.extra;
  if (event.user) event.user = event.user.id ? { id: event.user.id } : undefined;
  if (event.message) event.message = redactSecrets(event.message);
  for (const exception of event.exception?.values ?? []) {
    if (exception.value) exception.value = redactSecrets(exception.value);
  }
  if (event.breadcrumbs) {
    event.breadcrumbs = event.breadcrumbs
      .map(scrubBreadcrumb)
      .filter((crumb): crumb is Breadcrumb => crumb !== null);
  }
  return event;
}

/**
 * The app store could not be read when the upgrade sheet opened. The sheet says
 * so and offers a retry; this tells us, since an outage otherwise looks like a
 * store with nothing to sell (code-health audit CLAR-08).
 */
export function reportStoreUnavailable(error: unknown): void {
  if (!initialized) return;
  Sentry.captureException(error, { tags: { area: "store" } });
}

export function initMobileSentry(): void {
  if (initialized) return;
  const dsn = process.env.EXPO_PUBLIC_SENTRY_DSN?.trim();
  if (!dsn) return;

  Sentry.init({
    dsn,
    enabled: !__DEV__,
    tracesSampleRate: 0.1,
    sendDefaultPii: false,
    beforeSend: scrubSentryEvent,
    beforeBreadcrumb: scrubBreadcrumb,
  });
  initialized = true;
}

/**
 * A render crash an error boundary kept inside one message. The boundary
 * shows its fallback either way; this only reports it, and only when Sentry is
 * set up. The component stack names components, never their text.
 */
export function reportBoundaryError(
  boundary: "markdown" | "message_row",
  error: Error,
  componentStack?: string | null,
): void {
  if (!initialized) return;
  Sentry.captureException(error, {
    tags: { boundary },
    contexts: componentStack ? { react: { componentStack } } : undefined,
  });
}
