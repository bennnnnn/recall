import {
  formatScrollAwayBadge,
  getScrollThresholds,
  nextStreamingScrollDelay,
  resolveScrollAtBottom,
  shouldSchedulePostStreamScroll,
} from "@/lib/chatScrollLogic";

describe("chatScrollLogic", () => {
  it("getScrollThresholds scales with viewport and composer pad", () => {
    const small = getScrollThresholds({
      viewportHeight: 400,
      windowHeight: 800,
      listBottomPad: 0,
    });
    expect(small.hideAtBottom).toBe(64);
    expect(small.showWhenAway).toBeGreaterThanOrEqual(280);

    const padded = getScrollThresholds({
      viewportHeight: 400,
      windowHeight: 800,
      listBottomPad: 600,
    });
    expect(padded.showWhenAway).toBeGreaterThan(small.showWhenAway);
  });

  it("resolveScrollAtBottom hysteresis keeps prior state in dead zone", () => {
    expect(
      resolveScrollAtBottom({
        distanceFromBottom: 10,
        hideAtBottom: 64,
        showWhenAway: 280,
        currentlyAtBottom: false,
      }),
    ).toBe(true);
    expect(
      resolveScrollAtBottom({
        distanceFromBottom: 400,
        hideAtBottom: 64,
        showWhenAway: 280,
        currentlyAtBottom: true,
      }),
    ).toBe(false);
    expect(
      resolveScrollAtBottom({
        distanceFromBottom: 150,
        hideAtBottom: 64,
        showWhenAway: 280,
        currentlyAtBottom: true,
      }),
    ).toBe(true);
    expect(
      resolveScrollAtBottom({
        distanceFromBottom: 150,
        hideAtBottom: 64,
        showWhenAway: 280,
        currentlyAtBottom: false,
      }),
    ).toBe(false);
  });

  it("formatScrollAwayBadge caps at 9+", () => {
    expect(formatScrollAwayBadge(0)).toBeNull();
    expect(formatScrollAwayBadge(3)).toBe("3");
    expect(formatScrollAwayBadge(10)).toBe("9+");
  });

  it("shouldSchedulePostStreamScroll only when stream ends at bottom", () => {
    expect(shouldSchedulePostStreamScroll(true, false, true)).toBe(true);
    expect(shouldSchedulePostStreamScroll(false, false, true)).toBe(false);
    expect(shouldSchedulePostStreamScroll(true, true, true)).toBe(false);
    expect(shouldSchedulePostStreamScroll(true, false, false)).toBe(false);
  });

  it("nextStreamingScrollDelay converges toward 0 instead of resetting on sustained calls", () => {
    // A plain debounce recomputed from "now" on every call would return the
    // full 64ms every time draft updates keep arriving — never firing. This
    // must instead shrink as elapsed time grows, so a fast, steady stream
    // still gets a periodic catch-up rather than freezing until it pauses.
    expect(nextStreamingScrollDelay(0, 64)).toBe(64);
    expect(nextStreamingScrollDelay(30, 64)).toBe(34);
    expect(nextStreamingScrollDelay(60, 64)).toBe(4);
    expect(nextStreamingScrollDelay(64, 64)).toBe(0);
    // Already overdue (e.g. first call after a long pause, or a stale ref) —
    // never returns a negative delay.
    expect(nextStreamingScrollDelay(200, 64)).toBe(0);
  });
});
