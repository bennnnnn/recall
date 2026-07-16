import {
  clampMathWebViewHeight,
  COMPACT_MAX_HEIGHT,
  MAX_HEIGHT,
} from "@/lib/mathWebViewHeight";

describe("clampMathWebViewHeight", () => {
  describe("compact (final-answer) mode", () => {
    const opts = { compact: true, minHeight: 36, initialHeight: 36 };

    it("grows toward the reported height", () => {
      expect(clampMathWebViewHeight(60, 36, opts)).toBe(60);
    });

    it("BUG FIX regression: caps an overshooting report so the answer box cannot stretch into a tall pill", () => {
      // A pathological scrollHeight report (e.g. 300 from a font-swap reflow
      // in a narrow centered WebView) must be clamped to COMPACT_MAX_HEIGHT,
      // not 320 — that's what was stretching the gray box down over the
      // message action footer.
      expect(clampMathWebViewHeight(300, 36, opts)).toBe(COMPACT_MAX_HEIGHT);
      expect(COMPACT_MAX_HEIGHT).toBeLessThan(MAX_HEIGHT);
    });

    it("BUG FIX regression: shrinks back when the real height is smaller (self-corrects an overshoot)", () => {
      // Grow-only was the original bug — once overstretched, the box never
      // recovered. Compact answers are stable/non-streaming, so they must
      // track the real height in both directions.
      expect(clampMathWebViewHeight(40, 96, opts)).toBe(40);
    });

    it("ignores sub-pixel chatter", () => {
      expect(clampMathWebViewHeight(37, 36, opts)).toBeNull();
    });

    it("clamps to minHeight instead of going below it when shrinking from above", () => {
      // current 50, reported 10 → clamped up to minHeight 36, then applied
      // (shrink allowed in compact mode). Never returns a value below minHeight.
      expect(clampMathWebViewHeight(10, 50, opts)).toBe(36);
      // Already at minHeight: no change needed.
      expect(clampMathWebViewHeight(10, 36, opts)).toBeNull();
    });
  });

  describe("block-math (non-compact) mode", () => {
    const opts = { compact: false, minHeight: 48, initialHeight: 48 };

    it("grows to fit taller content up to MAX_HEIGHT", () => {
      expect(clampMathWebViewHeight(200, 48, opts)).toBe(200);
      expect(clampMathWebViewHeight(400, 48, opts)).toBe(MAX_HEIGHT);
    });

    it("stays grow-only — ignores a reported shrink (avoids streaming bubble jitter)", () => {
      expect(clampMathWebViewHeight(50, 200, opts)).toBeNull();
    });

    it("ignores chatter at the current height", () => {
      expect(clampMathWebViewHeight(201, 200, opts)).toBeNull();
    });
  });

  it("rejects non-positive / non-finite reports", () => {
    const opts = { compact: false, initialHeight: 48 };
    expect(clampMathWebViewHeight(0, 48, opts)).toBeNull();
    expect(clampMathWebViewHeight(-5, 48, opts)).toBeNull();
    expect(clampMathWebViewHeight(NaN, 48, opts)).toBeNull();
  });
});
