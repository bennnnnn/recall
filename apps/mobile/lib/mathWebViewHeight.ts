/**
 * Height policy for the math preview WebView.
 *
 * Extracted as a pure function so the grow/shrink + clamping logic is
 * unit-testable without a linked WebView native module (the JS test
 * environment can't run the onMessage path).
 */

/** Block math (matrices, aligned derivations) max height. */
export const MAX_HEIGHT = 320;
/**
 * Compact (final-answer) blocks are short, stable, non-streaming expressions
 * in a centered gray box. Cap tightly — a final answer is at most ~2 lines —
 * so an overshooting height report can't stretch the box into a tall vertical
 * pill that pushes the message action footer off screen.
 */
export const COMPACT_MAX_HEIGHT = 96;
/** Ignore sub-pixel / font-settle chatter so the chat list doesn't bounce. */
export const HEIGHT_EPSILON_PX = 4;

export type HeightClampOpts = {
  compact: boolean;
  minHeight?: number;
  initialHeight: number;
};

/**
 * Decide the next WebView height given a freshly reported `scrollHeight`.
 *
 * Returns `null` when the height should not change (chatter / grow-only
 * policy), otherwise the clamped height to apply.
 *
 * - Compact (final answers): track the real height — grow AND shrink —
 *   because these blocks are stable (not streaming); an overshoot must
 *   self-correct instead of permanently stretching the centered box.
 * - Block math: grow-only. Shrinking after fonts settle makes the whole
 *   assistant bubble jump mid-stream, so a reported shrink is ignored.
 */
export function clampMathWebViewHeight(
  reported: number,
  current: number,
  opts: HeightClampOpts,
): number | null {
  if (!Number.isFinite(reported) || reported <= 0) return null;
  const max = opts.compact ? COMPACT_MAX_HEIGHT : MAX_HEIGHT;
  const lower = opts.minHeight ?? opts.initialHeight;
  const clamped = Math.min(max, Math.max(lower, reported));
  if (opts.compact) {
    if (Math.abs(clamped - current) <= HEIGHT_EPSILON_PX) return null;
  } else {
    if (clamped <= current + HEIGHT_EPSILON_PX) return null;
  }
  return clamped;
}
