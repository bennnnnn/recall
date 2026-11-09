/**
 * The native splash stays up until the first screen can be drawn finished:
 * the session restored (or known to be signed out), the fonts in, and the
 * user's appearance and language applied. Never much longer than
 * SPLASH_MAX_MS: a launch that has to wait on the network shows its own
 * loading state rather than a frozen splash.
 *
 * That deadline is the one clock for the launch. When it passes, the root
 * layout stops waiting for fonts and draws (`subscribeLaunchDeadline`), and
 * the splash goes as soon as that tree is committed, so it never uncovers a
 * blank frame.
 */
import * as SplashScreen from "expo-splash-screen";
import { Platform } from "react-native";

import { isExpoGo } from "@/lib/expoRuntime";
import { createListenerSet } from "@/lib/listenerSet";
import { reportFailure } from "@/lib/sentry";

export const SPLASH_MAX_MS = 1_000;
/** If the app never draws at all (a crash before it), the splash still goes. */
const SPLASH_BACKSTOP_MS = 2_000;
/**
 * expo-splash-screen's Android exit: it always fades the native splash out, over
 * `setOptions`' `duration` (400 ms by default; its `fade` option is iOS only).
 */
const ANDROID_NATIVE_FADE_MS = 400;

type LaunchPart = "session" | "fonts" | "prefs";
const LAUNCH_PARTS: readonly LaunchPart[] = ["session", "fonts", "prefs"];

const ready = new Set<LaunchPart>();
let hidden = false;
let exited = false;
let deadlinePassed = false;
const deadline = createListenerSet();
const gone = createListenerSet();

function hideSplash(): void {
  if (hidden) return;
  hidden = true;
  clearTimeout(cap);
  clearTimeout(backstop);
  try {
    SplashScreen.hide();
  } catch (error) {
    // Reported, never thrown on: from a frame or a timer React Native takes it as fatal,
    // and a release build would close. The reveal still plays, so it never stays over the app.
    reportFailure("launch_splash_hide", error);
  }
  if (NATIVE_EXIT_MS > 0) setTimeout(finishExit, NATIVE_EXIT_MS);
  else finishExit();
}

function finishExit(): void {
  exited = true;
  gone.emit();
}

/**
 * How long the native splash takes to leave once hidden, so the launch reveal starts over
 * the bare page and is the only animation. iOS cuts it already (expo-splash-screen's
 * `fade` is off), so nothing changes there. Android would fade it over the reveal, a still
 * icon over the moving one: told 0 it goes in one frame. Expo Go refuses `setOptions`, so
 * there (or if the call fails) the reveal waits the default fade out.
 */
function nativeExitMs(): number {
  if (Platform.OS !== "android") return 0;
  if (isExpoGo()) return ANDROID_NATIVE_FADE_MS;
  try {
    SplashScreen.setOptions({ duration: 0 });
    return 0;
  } catch (error) {
    // This runs as the module loads: a throw here would leave the launch with no splash timers.
    reportFailure("launch_splash_set_options", error);
    return ANDROID_NATIVE_FADE_MS;
  }
}

/** One frame for the commit that made the first screen ready (and the layout it starts). */
function hideAfterThisFrame(): void {
  requestAnimationFrame(hideSplash);
}

function passDeadline(): void {
  deadlinePassed = true;
  deadline.emit();
  // Whatever else is missing shows its own state (the sign-in spinner, the
  // default theme). The fonts gate decides what is drawn: hide once it is open.
  if (ready.has("fonts")) hideAfterThisFrame();
}

// expo-splash-screen asks for this in global scope, before anything renders.
SplashScreen.preventAutoHideAsync().catch(() => {});
const NATIVE_EXIT_MS = nativeExitMs();
const cap = setTimeout(passDeadline, SPLASH_MAX_MS);
const backstop = setTimeout(hideSplash, SPLASH_BACKSTOP_MS);

/** True once the launch has waited as long as it may. */
export function launchDeadlinePassed(): boolean {
  return deadlinePassed;
}

/** Told once, when the launch has waited as long as it may. */
export function subscribeLaunchDeadline(listener: () => void): () => void {
  return deadline.subscribe(listener);
}

/** One part of the first screen is ready; the last one hides the splash. */
export function markLaunchReady(part: LaunchPart): void {
  if (hidden) return;
  ready.add(part);
  const drawn = deadlinePassed
    ? ready.has("fonts")
    : LAUNCH_PARTS.every((each) => ready.has(each));
  if (drawn) hideAfterThisFrame();
}

/** True once the native splash is gone: hidden, and its exit over. */
export function launchSplashHidden(): boolean {
  return exited;
}

/** Told once, when the native splash goes (the launch reveal starts then). */
export function subscribeLaunchSplashHidden(listener: () => void): () => void {
  return gone.subscribe(listener);
}
