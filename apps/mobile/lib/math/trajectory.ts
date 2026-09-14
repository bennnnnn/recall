/**
 * Geometry for the played-back trajectory dot.
 *
 * Split out of the component so it is a plain function the `lib` jest project
 * can assert directly. Inside the chart it runs in a Reanimated worklet on the
 * UI thread, hence the directive — a plain JS call from a worklet throws.
 */

export type ScreenPoint = { px: number; py: number };

/**
 * Position along the sampled path at `progress` (0 → 1).
 *
 * The solver samples both trajectory kinds at uniform time steps, so the array
 * index *is* the clock — even for `parametric`, where neither axis is time.
 * Walking it at a constant rate therefore reproduces the real motion (fast at
 * launch, slow at the apex) with no physics repeated here.
 *
 * Progress is clamped: a spring or an interrupted timing can overshoot, and an
 * out-of-range index would read `undefined` and render the dot at NaN.
 */
export function trajectoryPointAt(
  points: readonly ScreenPoint[],
  progress: number,
): ScreenPoint {
  "worklet";
  const last = points.length - 1;
  if (last < 0) return { px: 0, py: 0 };
  if (last === 0) return points[0];
  const clamped = progress < 0 ? 0 : progress > 1 ? 1 : progress;
  const at = clamped * last;
  const lo = Math.floor(at);
  const hi = lo + 1 > last ? last : lo + 1;
  const frac = at - lo;
  const a = points[lo];
  const b = points[hi];
  return {
    px: a.px + (b.px - a.px) * frac,
    py: a.py + (b.py - a.py) * frac,
  };
}

/** On-screen length of the sampled path, for the trail's dash offset. */
export function trajectoryPathLength(points: readonly ScreenPoint[]): number {
  let total = 0;
  for (let i = 1; i < points.length; i += 1) {
    total += Math.hypot(points[i].px - points[i - 1].px, points[i].py - points[i - 1].py);
  }
  return total;
}
