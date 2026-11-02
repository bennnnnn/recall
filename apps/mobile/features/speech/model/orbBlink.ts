/**
 * When the live talk face blinks. The eyes look straight ahead and hold still; a person
 * blinks every few seconds, never on a beat, so each gap is drawn afresh from 3 to 6 s.
 * A blink is a quick close and open, about 150 ms in all.
 */

const BLINK_GAP_MIN_MS = 3000;
const BLINK_GAP_MAX_MS = 6000;
export const BLINK_CLOSE_MS = 70;
export const BLINK_OPEN_MS = 80;
/** How far the eyes squash when shut: a sliver stays, so they read as closed, not gone. */
export const BLINK_SHUT_SCALE = 0.1;

/** The wait before the next blink; `random` is 0 (shortest) to 1 (longest). */
export function nextBlinkGapMs(random: () => number = Math.random): number {
  const r = Math.min(1, Math.max(0, random()));
  return Math.round(BLINK_GAP_MIN_MS + r * (BLINK_GAP_MAX_MS - BLINK_GAP_MIN_MS));
}

/** Calls `onBlink` after each fresh gap until the returned stop is called. */
export function scheduleBlinks(onBlink: () => void, random: () => number = Math.random): () => void {
  let timer: ReturnType<typeof setTimeout> | null = null;
  let stopped = false;
  const wait = () => {
    timer = setTimeout(() => {
      if (stopped) return;
      onBlink();
      wait();
    }, nextBlinkGapMs(random));
  };
  wait();
  return () => {
    stopped = true;
    if (timer != null) clearTimeout(timer);
  };
}
