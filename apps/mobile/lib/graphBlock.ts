import { toSuperscript } from "@/lib/unicodeSupSub";

export type NumberLineInterval = {
  start: number | null;
  end: number | null;
  start_inclusive: boolean;
  end_inclusive: boolean;
};

export type GraphSpec = {
  type: "function" | "vertical" | "number_line";
  expr: string;
  variable?: string;
  x_min?: number;
  x_max?: number;
  /** Vertical line at this x (when type is "vertical"). */
  x?: number;
  y_min?: number;
  y_max?: number;
  title?: string | null;
  points: [number, number][];
  // points split at a likely discontinuity (e.g. a tan(x) vertical
  // asymptote) — present only when the backend detected a real gap.
  // Undefined/empty means "one continuous curve," same as before this
  // field existed.
  segments?: [number, number][][];
  // Optional second curve for a direct comparison plot ("graph y=x^2 and
  // y=2x on the same axes") — undefined means "single-curve graph," same
  // as every fence before this field existed.
  expr2?: string;
  points2?: [number, number][];
  segments2?: [number, number][][];
  label?: string;
  label2?: string;
  intervals?: NumberLineInterval[];
};

/** Match backend `GraphBlockSpec.points` max; chat samples default lower. */
export const MAX_GRAPH_POINTS = 500;
export const MAX_GRAPH_EXPR_LENGTH = 256;

function normalizePoint(raw: unknown): [number, number] | null {
  if (!Array.isArray(raw) || raw.length < 2) return null;
  const x = Number(raw[0]);
  const y = Number(raw[1]);
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
  return [x, y];
}

/** Evenly subsample so oversized backend dumps still draw a smooth curve. */
export function downsamplePoints(
  points: [number, number][],
  maxPoints: number,
): [number, number][] {
  if (points.length <= maxPoints || maxPoints < 2) return points;
  const last = points.length - 1;
  const out: [number, number][] = [];
  for (let i = 0; i < maxPoints; i++) {
    const idx = Math.round((i * last) / (maxPoints - 1));
    out.push(points[idx]);
  }
  return out;
}

function parseVerticalGraph(row: Record<string, unknown>): GraphSpec | null {
  const x = Number(row.x);
  if (!Number.isFinite(x)) return null;
  const yMin = Number(row.y_min ?? -10);
  const yMax = Number(row.y_max ?? 10);
  if (!Number.isFinite(yMin) || !Number.isFinite(yMax) || yMax <= yMin) return null;
  const expr = String(row.expr ?? `x = ${x}`).trim() || `x = ${x}`;
  if (expr.length > MAX_GRAPH_EXPR_LENGTH) return null;
  const pointsRaw = row.points;
  let points: [number, number][] = [
    [x, yMin],
    [x, yMax],
  ];
  if (Array.isArray(pointsRaw) && pointsRaw.length >= 2) {
    const parsed = pointsRaw
      .map(normalizePoint)
      .filter((p): p is [number, number] => p != null);
    if (parsed.length >= 2) points = parsed;
  }
  return {
    type: "vertical",
    expr,
    variable: String(row.variable ?? "x"),
    x,
    y_min: yMin,
    y_max: yMax,
    x_min: Number(row.x_min ?? x - 5),
    x_max: Number(row.x_max ?? x + 5),
    title: row.title != null ? String(row.title) : expr,
    points,
  };
}

function parseBound(raw: unknown): number | null {
  if (raw == null) return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}

function parseNumberLineGraph(row: Record<string, unknown>): GraphSpec | null {
  const expr = String(row.expr ?? "").trim();
  if (!expr || expr.length > MAX_GRAPH_EXPR_LENGTH) return null;
  const rawIntervals = Array.isArray(row.intervals) ? row.intervals : [];
  if (rawIntervals.length > 8) return null;
  const intervals: NumberLineInterval[] = [];
  for (const item of rawIntervals) {
    if (!item || typeof item !== "object") return null;
    const iv = item as Record<string, unknown>;
    const start = parseBound(iv.start);
    const end = parseBound(iv.end);
    if (start != null && end != null && start > end) return null;
    intervals.push({
      start,
      end,
      start_inclusive: Boolean(iv.start_inclusive),
      end_inclusive: Boolean(iv.end_inclusive),
    });
  }
  return {
    type: "number_line",
    expr,
    variable: String(row.variable ?? "x"),
    title: row.title != null ? String(row.title) : expr,
    points: [],
    intervals,
  };
}

function parsePoints(raw: unknown): [number, number][] {
  if (!Array.isArray(raw)) return [];
  return downsamplePoints(
    raw.map(normalizePoint).filter((p): p is [number, number] => p != null),
    MAX_GRAPH_POINTS,
  );
}

function parseSegments(raw: unknown): [number, number][][] | undefined {
  if (!Array.isArray(raw) || raw.length > MAX_GRAPH_POINTS) return undefined;
  const parsed = raw
    .map((seg) => (Array.isArray(seg) ? parsePoints(seg) : []))
    .filter((seg) => seg.length > 0);
  // Only meaningful with a real gap (2+ pieces) — a single segment is just
  // `points` again, so leave segments unset and render the plain continuous
  // polyline instead.
  return parsed.length > 1 ? parsed : undefined;
}

export function parseGraphSpec(raw: string): GraphSpec | null {
  try {
    const data = JSON.parse(raw.trim()) as unknown;
    if (!data || typeof data !== "object") return null;
    const row = data as Record<string, unknown>;
    if (row.type === "vertical") {
      return parseVerticalGraph(row);
    }
    if (row.type === "number_line") {
      return parseNumberLineGraph(row);
    }
    if (row.type !== "function") return null;
    const expr = String(row.expr ?? "").trim();
    if (!expr || expr.length > MAX_GRAPH_EXPR_LENGTH) return null;
    const points = parsePoints(row.points);
    // A function curve needs 2+ points to draw a line, but marking a single
    // coordinate ("plot the point (2, 3)") is a single point by definition.
    if (points.length < 1) return null;

    const segments = parseSegments(row.segments);

    // Optional second curve — undefined/incomplete means "single-curve
    // graph," same as every fence before this field existed.
    const expr2Raw = row.expr2 != null ? String(row.expr2).trim() : "";
    const points2 = expr2Raw ? parsePoints(row.points2) : [];
    const hasCurve2 = Boolean(expr2Raw) && expr2Raw.length <= MAX_GRAPH_EXPR_LENGTH && points2.length >= 1;

    return {
      type: "function",
      expr,
      variable: String(row.variable ?? "x"),
      x_min: Number(row.x_min ?? points[0][0]),
      x_max: Number(row.x_max ?? points[points.length - 1][0]),
      title: row.title != null ? String(row.title) : null,
      points,
      segments,
      expr2: hasCurve2 ? expr2Raw : undefined,
      points2: hasCurve2 ? points2 : undefined,
      segments2: hasCurve2 ? parseSegments(row.segments2) : undefined,
      label: row.label != null ? String(row.label) : undefined,
      label2: hasCurve2 && row.label2 != null ? String(row.label2) : undefined,
    };
  } catch {
    return null;
  }
}

export function graphBounds(
  points: [number, number][],
  // Second curve's points, when present — folded into the same min/max so
  // both curves share one consistent axis scale instead of each being
  // (re)bounded to just its own range.
  extraPoints?: [number, number][],
): {
  xMin: number;
  xMax: number;
  yMin: number;
  yMax: number;
} {
  let xMin = points[0][0];
  let xMax = points[0][0];
  let yMin = points[0][1];
  let yMax = points[0][1];
  for (const [x, y] of points) {
    xMin = Math.min(xMin, x);
    xMax = Math.max(xMax, x);
    yMin = Math.min(yMin, y);
    yMax = Math.max(yMax, y);
  }
  for (const [x, y] of extraPoints ?? []) {
    xMin = Math.min(xMin, x);
    xMax = Math.max(xMax, x);
    yMin = Math.min(yMin, y);
    yMax = Math.max(yMax, y);
  }
  // A single point (or several points sharing an x or y value) collapses
  // that axis's range to zero — pad it symmetrically so the point renders
  // centered instead of glued to the chart's edge (mapGraphPoint's `|| 1`
  // divide-by-zero guard alone would put it flush at the left/bottom).
  if (yMin === yMax) {
    yMin -= 1;
    yMax += 1;
  }
  if (xMin === xMax) {
    xMin -= 1;
    xMax += 1;
  }
  return { xMin, xMax, yMin, yMax };
}

/** Viewport for a number line: integers both sides of 0, room for arrows. */
export function numberLineBounds(intervals: NumberLineInterval[]): {
  xMin: number;
  xMax: number;
} {
  const finite: number[] = [0];
  let rayLeft = false;
  let rayRight = false;
  for (const iv of intervals) {
    if (iv.start == null) rayLeft = true;
    else finite.push(iv.start);
    if (iv.end == null) rayRight = true;
    else finite.push(iv.end);
  }
  let xMin = Math.min(...finite);
  let xMax = Math.max(...finite);
  xMin = Math.floor(xMin) - 1;
  xMax = Math.ceil(xMax) + 1;
  if (rayLeft) xMin -= 2;
  if (rayRight) xMax += 2;
  // Don't let the axis start at 0 — a number line continues through negatives.
  if (xMin > -2) xMin = -2;
  if (xMax < 2) xMax = 2;
  if (xMax - xMin < 6) {
    const extra = 6 - (xMax - xMin);
    xMin -= Math.ceil(extra / 2);
    xMax += Math.floor(extra / 2);
  }
  return { xMin, xMax };
}

/** Integer tick marks inside the viewport (capped so labels don't collide). */
export function numberLineTicks(xMin: number, xMax: number): number[] {
  const start = Math.floor(xMin) + 1;
  const end = Math.ceil(xMax) - 1;
  if (end < start) return [];
  const count = end - start + 1;
  const push = (n: number, into: number[]) => {
    into.push(n === 0 ? 0 : n);
  };
  if (count <= 11) {
    const out: number[] = [];
    for (let n = start; n <= end; n += 1) push(n, out);
    return out;
  }
  const step = Math.ceil(count / 9);
  const out: number[] = [];
  for (let n = start; n <= end; n += step) push(n, out);
  if (out[out.length - 1] !== end) push(end, out);
  if (!out.includes(0) && 0 >= start && 0 <= end) {
    push(0, out);
    out.sort((a, b) => a - b);
  }
  return out;
}

/** ``x >= 3`` → ``x ≥ 3`` for number-line titles. */
export function formatInequalityExpr(expr: string): string {
  let out = "";
  let i = 0;
  const src = expr.trim();
  while (i < src.length) {
    const two = src.slice(i, i + 2);
    if (two === ">=") {
      out += "≥";
      i += 2;
      continue;
    }
    if (two === "<=") {
      out += "≤";
      i += 2;
      continue;
    }
    out += src[i];
    i += 1;
  }
  return out;
}

const AXIS_PAD_RATIO = 0.08;

/** Expand data bounds so (0, 0) is in view and axes aren't glued to the frame. */
export function expandBoundsForAxes(
  bounds: ReturnType<typeof graphBounds>,
): ReturnType<typeof graphBounds> {
  let { xMin, xMax, yMin, yMax } = bounds;
  if (xMin > 0) xMin = 0;
  if (xMax < 0) xMax = 0;
  if (yMin > 0) yMin = 0;
  if (yMax < 0) yMax = 0;
  const xSpan = xMax - xMin || 1;
  const ySpan = yMax - yMin || 1;
  return {
    xMin: xMin - xSpan * AXIS_PAD_RATIO,
    xMax: xMax + xSpan * AXIS_PAD_RATIO,
    yMin: yMin - ySpan * AXIS_PAD_RATIO,
    yMax: yMax + ySpan * AXIS_PAD_RATIO,
  };
}

/** Turn SymPy/Python ``3*x**2 - 12`` into a readable ``3x² - 12``. */
export function formatGraphExpr(expr: string): string {
  const src = expr.trim();
  let out = "";
  let i = 0;
  while (i < src.length) {
    if (src[i] === "*" && src[i + 1] === "*") {
      let j = i + 2;
      let exp = "";
      if (src[j] === "-") {
        exp = "-";
        j += 1;
      }
      while (j < src.length && src[j] >= "0" && src[j] <= "9") {
        exp += src[j];
        j += 1;
      }
      const sup = exp && !exp.endsWith("-") ? toSuperscript(exp) : null;
      if (sup) {
        out += sup;
        i = j;
        continue;
      }
    }
    out += src[i];
    i += 1;
  }
  let stripped = "";
  for (let k = 0; k < out.length; k += 1) {
    const ch = out[k];
    if (ch === "*" && k > 0 && k + 1 < out.length) {
      const prev = out[k - 1];
      const next = out[k + 1];
      const prevOk =
        (prev >= "0" && prev <= "9") ||
        (prev >= "A" && prev <= "Z") ||
        (prev >= "a" && prev <= "z") ||
        prev === ")";
      const nextOk =
        (next >= "A" && next <= "Z") ||
        (next >= "a" && next <= "z") ||
        next === "(";
      if (prevOk && nextOk) continue;
    }
    stripped += ch;
  }
  return stripped;
}

export function mapGraphPoint(
  x: number,
  y: number,
  bounds: ReturnType<typeof graphBounds>,
  width: number,
  height: number,
  pad = 28,
): { px: number; py: number } {
  const innerW = width - pad * 2;
  const innerH = height - pad * 2;
  const px =
    pad + ((x - bounds.xMin) / (bounds.xMax - bounds.xMin || 1)) * innerW;
  const py =
    pad +
    innerH -
    ((y - bounds.yMin) / (bounds.yMax - bounds.yMin || 1)) * innerH;
  return { px, py };
}

export function graphPolylinePoints(
  points: [number, number][],
  width: number,
  height: number,
  // Optional precomputed bounds — required when rendering multiple segments
  // of the same curve, so every segment maps against the same shared axis
  // scale instead of each one being (re)bounded to just its own points.
  bounds: ReturnType<typeof graphBounds> = graphBounds(points),
): string {
  return points
    .map(([x, y]) => {
      const { px, py } = mapGraphPoint(x, y, bounds, width, height);
      return `${px},${py}`;
    })
    .join(" ");
}
