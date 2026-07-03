/** Optional Sentry init — no-op when EXPO_PUBLIC_SENTRY_DSN is unset. */

import * as Sentry from "@sentry/react-native";

let initialized = false;

export function initMobileSentry(): void {
  if (initialized) return;
  const dsn = process.env.EXPO_PUBLIC_SENTRY_DSN?.trim();
  if (!dsn) return;

  Sentry.init({
    dsn,
    enabled: !__DEV__,
    tracesSampleRate: 0.1,
    sendDefaultPii: false,
  });
  initialized = true;
}
