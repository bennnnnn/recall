/** Optional Sentry init — no-op when EXPO_PUBLIC_SENTRY_DSN is unset. */

let initialized = false;

export function initMobileSentry(): void {
  if (initialized) return;
  const dsn = process.env.EXPO_PUBLIC_SENTRY_DSN?.trim();
  if (!dsn) return;

  try {
    // Optional peer — install @sentry/react-native to enable crash reporting.
    // eslint-disable-next-line @typescript-eslint/no-require-imports, @typescript-eslint/no-explicit-any
    const Sentry = require("@sentry/react-native") as any;
    Sentry.init({
      dsn,
      enabled: !__DEV__,
      tracesSampleRate: 0.1,
      sendDefaultPii: false,
    });
    initialized = true;
  } catch {
    // @sentry/react-native not installed — skip silently
  }
}
