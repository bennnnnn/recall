import { activateKeepAwakeAsync, deactivateKeepAwake } from "expo-keep-awake";

import { reportFailure } from "@/lib/sentry";

/**
 * The screen stays on while something the user is waiting on hands-free runs: a live
 * talk call (which hangs up when the app leaves the screen), a live dictation, a picture
 * being drawn. The phone's auto-lock would otherwise end them after 30 s to a minute.
 *
 * Each owner holds its own tag, so one ending never lets the screen sleep under another;
 * the screen sleeps again once every tag is released (expo-keep-awake keeps the set).
 */
const held = new Set<string>();

/** Keeps the screen on under `tag` until `releaseScreenAwake(tag)`. Holding twice is one hold. */
export function holdScreenAwake(tag: string): void {
  if (held.has(tag)) return;
  held.add(tag);
  // Android refuses with no activity (a moment between screens): the screen may then lock.
  activateKeepAwakeAsync(tag).catch((error: unknown) => reportFailure("keep_awake", error));
}

/** Lets the screen sleep again as far as `tag` goes. Releasing a tag not held does nothing. */
export function releaseScreenAwake(tag: string): void {
  if (!held.delete(tag)) return;
  deactivateKeepAwake(tag).catch((error: unknown) => reportFailure("keep_awake", error));
}

/** Sign-out: nothing of the last account keeps the screen on. */
export function releaseAllScreenAwake(): void {
  for (const tag of [...held]) releaseScreenAwake(tag);
}
