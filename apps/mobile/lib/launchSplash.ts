/**
 * The native splash stays up until the first screen can be drawn finished:
 * the session restored (or known to be signed out), the fonts in, and the
 * user's appearance and language applied. Never longer than SPLASH_MAX_MS: a
 * launch that has to wait on the network shows its own loading state rather
 * than a frozen splash.
 */
import * as SplashScreen from "expo-splash-screen";

export const SPLASH_MAX_MS = 1_000;

export type LaunchPart = "session" | "fonts" | "prefs";
const LAUNCH_PARTS: readonly LaunchPart[] = ["session", "fonts", "prefs"];

const ready = new Set<LaunchPart>();
let hidden = false;

function hideSplash(): void {
  if (hidden) return;
  hidden = true;
  clearTimeout(cap);
  SplashScreen.hide();
}

// expo-splash-screen asks for this in global scope, before anything renders.
SplashScreen.preventAutoHideAsync().catch(() => {});
const cap = setTimeout(hideSplash, SPLASH_MAX_MS);

/** One part of the first screen is ready; the last one hides the splash. */
export function markLaunchReady(part: LaunchPart): void {
  if (hidden) return;
  ready.add(part);
  if (!LAUNCH_PARTS.every((each) => ready.has(each))) return;
  // One frame for the commit that made it ready (and any layout it starts).
  requestAnimationFrame(hideSplash);
}
