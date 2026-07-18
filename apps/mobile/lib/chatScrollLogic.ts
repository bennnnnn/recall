export const SCROLL_HIDE_AT_BOTTOM = 64;
export const SCROLL_SHOW_MIN_AWAY = 280;
export const SCROLL_SHOW_VIEWPORT_RATIO = 0.28;

export function getScrollThresholds(options: {
  viewportHeight: number;
  windowHeight: number;
  listBottomPad: number;
}): { hideAtBottom: number; showWhenAway: number } {
  const viewport = options.viewportHeight || options.windowHeight * 0.55;
  const hideAtBottom = Math.max(
    SCROLL_HIDE_AT_BOTTOM,
    options.listBottomPad * 0.2,
  );
  const showWhenAway = Math.max(
    SCROLL_SHOW_MIN_AWAY,
    viewport * SCROLL_SHOW_VIEWPORT_RATIO,
    options.listBottomPad * 0.55,
  );
  return { hideAtBottom, showWhenAway };
}

export function resolveScrollAtBottom(options: {
  distanceFromBottom: number;
  hideAtBottom: number;
  showWhenAway: number;
  currentlyAtBottom: boolean;
}): boolean {
  if (options.distanceFromBottom <= options.hideAtBottom) return true;
  if (options.distanceFromBottom >= options.showWhenAway) return false;
  return options.currentlyAtBottom;
}

export function formatScrollAwayBadge(count: number): string | null {
  if (count <= 0) return null;
  return count > 9 ? "9+" : String(count);
}

/** Scroll once after stream ends — not on every draft clear / layout tick. */
export function shouldSchedulePostStreamScroll(
  wasStreamActive: boolean,
  streamActive: boolean,
  atBottom: boolean,
): boolean {
  return wasStreamActive && !streamActive && atBottom;
}

/**
 * Throttle (not debounce) delay for the streaming catch-up scroll. A plain
 * debounce — reset on every call — would never fire while draft updates keep
 * arriving faster than `throttleMs` (normal for a fast provider), freezing
 * the view mid-stream until generation paused. Recomputing the remaining
 * wait from elapsed time on every call instead makes it converge toward 0
 * (and then fire) rather than being pushed out indefinitely.
 */
export function nextStreamingScrollDelay(elapsedMs: number, throttleMs: number): number {
  return Math.max(0, throttleMs - elapsedMs);
}
