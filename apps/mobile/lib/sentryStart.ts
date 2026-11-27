/**
 * Starts Sentry as this module runs. app/_layout.tsx imports it first, so the SDK's
 * handlers are on before any other app module runs and before the first render: a crash
 * at launch, after a bad over-the-air update or in the native code from then on, is
 * reported. Expo Router's entry has loaded `expo` by then, so the SDK wraps the fetch
 * the app really uses. Without a DSN it does nothing and the SDK is never loaded.
 *
 * With a DSN it costs about 90 ms before the first render (loading the SDK about 78 ms,
 * `init` about 15 ms; three cold launches of a production-mode bundle on an iPhone 17 Pro
 * Max Simulator, 2026-11-27). That work used to run once the launch was idle.
 */
import { initMobileSentry } from "@/lib/sentry";

initMobileSentry();
