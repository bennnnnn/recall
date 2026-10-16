const SCROLL_HIDE_AT_BOTTOM = 64;
const SCROLL_SHOW_MIN_AWAY = 280;
const SCROLL_SHOW_VIEWPORT_RATIO = 0.28;

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

/** Short threads fit the viewport — scrollToEnd would pin them to the composer. */
export function shouldScrollToEndWhenPinned(maxOffset: number): boolean {
  return maxOffset > 0;
}

/**
 * A short thread that was laid out from the bottom stays there with offset 0,
 * because the extra top pad is not scrollable. Once that pad is gone, pull a
 * leftover offset back to the header. A thread taller than the screen opens
 * on the latest message once, then the streaming pin takes over.
 */
export function resolveListAnchor(options: {
  contentHeight: number;
  viewportHeight: number;
  scrollOffset: number;
  atBottom: boolean;
  pinnedOverflow: boolean;
}): { action: "top" | "end" | "none"; pinnedOverflow: boolean } {
  if (options.viewportHeight <= 0 || options.contentHeight <= 0) {
    return { action: "none", pinnedOverflow: options.pinnedOverflow };
  }
  const maxOffset = Math.max(0, options.contentHeight - options.viewportHeight);
  if (!shouldScrollToEndWhenPinned(maxOffset)) {
    return {
      action: options.scrollOffset > 1 ? "top" : "none",
      pinnedOverflow: false,
    };
  }
  if (options.pinnedOverflow || !options.atBottom) {
    return { action: "none", pinnedOverflow: options.pinnedOverflow };
  }
  return { action: "end", pinnedOverflow: true };
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
