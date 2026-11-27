/**
 * Starts Sentry as this module runs. app/_layout.tsx imports it first, so the SDK's
 * handlers are on before any other app module runs and before the first render: a crash
 * at launch, after a bad over-the-air update or in the native code from then on, is
 * reported. Expo Router's entry has loaded `expo` by then, so the SDK wraps the fetch
 * the app really uses. Without a DSN it does nothing and the SDK is never loaded.
 */
import { initMobileSentry } from "@/lib/sentry";

initMobileSentry();
