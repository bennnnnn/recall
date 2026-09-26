import {
  formatAxisNumber,
  graphAxisTicks,
  graphTickCount,
  mapGraphPoint,
} from "@/lib/math/graphBlock";

/**
 * Geometry for the played-back trajectory dot.
 *
 * Split out of the component so it is a plain function the `lib` jest project
 * can assert directly. Inside the chart it runs in a Reanimated worklet on the
 * UI thread, hence the directive — a plain JS call from a worklet throws.
 */

export type ScreenPoint = { px: number; py: number };

export type TrajectoryBounds = {
  xMin: number;
  xMax: number;
  yMin: number;
  yMax: number;
};

export type TrajectoryAxisLabel = {
  value: number;
  text: string;
  px: number;
  py: number;
};

export type TrajectoryAxisLayout = {
  origin: ScreenPoint;
  xAxisY: number;
  yAxisX: number;
  xTicks: TrajectoryAxisLabel[];
  yTicks: TrajectoryAxisLabel[];
};

/** Put the horizontal caption in its own band below the plotted motion. */
export function trajectoryAxisCaptionPosition(
  labelWidth: number,
  width: number,
  height: number,
  pad: number,
): ScreenPoint {
  return {
    px: Math.max(4, width - pad - Math.max(0, labelWidth)),
    py: height - 4,
  };
}

/**
 * Static trajectory-axis geometry shared by the native Skia renderer and its
 * tests. Text anchoring is applied by the renderer after measuring the font;
 * these coordinates remain the exact mathematical tick positions.
 */
export function trajectoryAxisLayout(
  bounds: TrajectoryBounds,
  width: number,
  height: number,
  pad = 28,
): TrajectoryAxisLayout {
  const origin = mapGraphPoint(0, 0, bounds, width, height, pad);
  const xTicks = graphAxisTicks(
    bounds.xMin,
    bounds.xMax,
    graphTickCount(bounds.xMin, bounds.xMax),
    true,
  )
    .filter((value) => Math.abs(value) >= 1e-9)
    .map((value) => {
      const { px } = mapGraphPoint(value, 0, bounds, width, height, pad);
      return { value, text: formatAxisNumber(value, true), px, py: origin.py + 16 };
    });
  const yTicks = graphAxisTicks(
    bounds.yMin,
    bounds.yMax,
    graphTickCount(bounds.yMin, bounds.yMax),
    true,
  )
    .filter((value) => Math.abs(value) >= 1e-9)
    .map((value) => {
      const { py } = mapGraphPoint(0, value, bounds, width, height, pad);
      return { value, text: formatAxisNumber(value, true), px: origin.px - 6, py: py + 4 };
    })
    .filter((tick) => tick.py - 4 >= pad + 12);
  return {
    origin,
    xAxisY: origin.py,
    yAxisX: origin.px,
    xTicks,
    yTicks,
  };
}

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
