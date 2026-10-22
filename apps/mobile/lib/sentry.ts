/**
 * Optional Sentry: a no-op when EXPO_PUBLIC_SENTRY_DSN is unset. Same rule as
 * the API's (apps/api/app/core/sentry.py): an event carries what broke, never
 * what the user wrote, what the model answered, a request body or a token.
 *
 * The SDK (about 750 KB) loads inside the deferred init, not at launch. Until
 * then Sentry has no global handler, as before; a boundary crash reported in
 * that window waits in a short queue and is sent once the SDK is up.
 */

import type { Breadcrumb, ErrorEvent } from "@sentry/react-native";

type SentrySdk = typeof import("@sentry/react-native");

/** The SDK once `init` has run. */
let sdk: SentrySdk | null = null;
let starting: Promise<void> | null = null;

/** A crash loop before init keeps only the first few. */
const MAX_EARLY_REPORTS = 10;
const earlyReports: ((sentry: SentrySdk) => void)[] = [];

function configuredDsn(): string | undefined {
  return process.env.EXPO_PUBLIC_SENTRY_DSN?.trim() || undefined;
}

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

/** Loads and starts the SDK once; resolves when it is up, or at once without a DSN. */
export function initMobileSentry(): Promise<void> {
  const dsn = configuredDsn();
  if (!dsn) return Promise.resolve();
  starting ??= import("@sentry/react-native").then(
    (Sentry) => {
      Sentry.init({
        dsn,
        enabled: !__DEV__,
        tracesSampleRate: 0.1,
        sendDefaultPii: false,
        beforeSend: scrubSentryEvent,
        beforeBreadcrumb: scrubBreadcrumb,
      });
      sdk = Sentry;
      for (const report of earlyReports.splice(0)) report(Sentry);
    },
    () => {
      // The SDK could not load (a dev bundle offline): the next init tries again.
      starting = null;
    },
  );
  return starting;
}

/**
 * A render crash an error boundary kept inside one message. The boundary
 * shows its fallback either way; this only reports it, and only when Sentry is
 * configured (before the SDK is up, it waits in the queue). The component
 * stack names components, never their text.
 */
export function reportBoundaryError(
  boundary: "markdown" | "message_row",
  error: Error,
  componentStack?: string | null,
): void {
  const capture = (Sentry: SentrySdk) => {
    Sentry.captureException(error, {
      tags: { boundary },
      contexts: componentStack ? { react: { componentStack } } : undefined,
    });
  };
  if (sdk) {
    capture(sdk);
    return;
  }
  if (!configuredDsn() || earlyReports.length >= MAX_EARLY_REPORTS) return;
  earlyReports.push(capture);
}
