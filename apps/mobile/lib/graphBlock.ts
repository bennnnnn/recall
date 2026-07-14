export type GraphSpec = {
  type: "function";
  expr: string;
  variable?: string;
  x_min?: number;
  x_max?: number;
  title?: string | null;
  points: [number, number][];
  // points split at a likely discontinuity (e.g. a tan(x) vertical
  // asymptote) — present only when the backend detected a real gap.
  // Undefined/empty means "one continuous curve," same as before this
  // field existed.
  segments?: [number, number][][];
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

export function parseGraphSpec(raw: string): GraphSpec | null {
  try {
    const data = JSON.parse(raw.trim()) as unknown;
    if (!data || typeof data !== "object") return null;
    const row = data as Record<string, unknown>;
    if (row.type !== "function") return null;
    const expr = String(row.expr ?? "").trim();
    if (!expr || expr.length > MAX_GRAPH_EXPR_LENGTH) return null;
    const pointsRaw = row.points;
    if (!Array.isArray(pointsRaw) || pointsRaw.length < 1) {
      return null;
    }
    const points = downsamplePoints(
      pointsRaw
        .map(normalizePoint)
        .filter((p): p is [number, number] => p != null),
      MAX_GRAPH_POINTS,
    );
    // A function curve needs 2+ points to draw a line, but marking a single
    // coordinate ("plot the point (2, 3)") is a single point by definition.
    if (points.length < 1) return null;

    const segmentsRaw = row.segments;
    let segments: [number, number][][] | undefined;
    if (Array.isArray(segmentsRaw) && segmentsRaw.length <= MAX_GRAPH_POINTS) {
      const parsed = segmentsRaw
        .map((seg) =>
          Array.isArray(seg)
            ? downsamplePoints(
                seg
                  .map(normalizePoint)
                  .filter((p): p is [number, number] => p != null),
                MAX_GRAPH_POINTS,
              )
            : [],
        )
        .filter((seg) => seg.length > 0);
      // Only meaningful with a real gap (2+ pieces) — a single segment is
      // just `points` again, so leave segments unset and render the plain
      // continuous polyline instead.
      if (parsed.length > 1) segments = parsed;
    }

    return {
      type: "function",
      expr,
      variable: String(row.variable ?? "x"),
      x_min: Number(row.x_min ?? points[0][0]),
      x_max: Number(row.x_max ?? points[points.length - 1][0]),
      title: row.title != null ? String(row.title) : null,
      points,
      segments,
    };
  } catch {
    return null;
  }
}

export function graphBounds(points: [number, number][]): {
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
