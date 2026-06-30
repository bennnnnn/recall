export type GraphSpec = {
  type: "function";
  expr: string;
  variable?: string;
  x_min?: number;
  x_max?: number;
  title?: string | null;
  points: [number, number][];
};

function normalizePoint(raw: unknown): [number, number] | null {
  if (!Array.isArray(raw) || raw.length < 2) return null;
  const x = Number(raw[0]);
  const y = Number(raw[1]);
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
  return [x, y];
}

export function parseGraphSpec(raw: string): GraphSpec | null {
  try {
    const data = JSON.parse(raw.trim()) as unknown;
    if (!data || typeof data !== "object") return null;
    const row = data as Record<string, unknown>;
    if (row.type !== "function") return null;
    const expr = String(row.expr ?? "").trim();
    if (!expr) return null;
    const pointsRaw = row.points;
    if (!Array.isArray(pointsRaw) || pointsRaw.length < 2) return null;
    const points = pointsRaw
      .map(normalizePoint)
      .filter((p): p is [number, number] => p != null);
    if (points.length < 2) return null;
    return {
      type: "function",
      expr,
      variable: String(row.variable ?? "x"),
      x_min: Number(row.x_min ?? points[0][0]),
      x_max: Number(row.x_max ?? points[points.length - 1][0]),
      title: row.title != null ? String(row.title) : null,
      points,
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
  if (yMin === yMax) {
    yMin -= 1;
    yMax += 1;
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
  const px = pad + ((x - bounds.xMin) / (bounds.xMax - bounds.xMin || 1)) * innerW;
  const py = pad + innerH - ((y - bounds.yMin) / (bounds.yMax - bounds.yMin || 1)) * innerH;
  return { px, py };
}

export function graphPolylinePoints(
  points: [number, number][],
  width: number,
  height: number,
): string {
  const bounds = graphBounds(points);
  return points
    .map(([x, y]) => {
      const { px, py } = mapGraphPoint(x, y, bounds, width, height);
      return `${px},${py}`;
    })
    .join(" ");
}
