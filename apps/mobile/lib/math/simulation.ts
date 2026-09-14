/**
 * Parsing and geometry for the `simulation` fence.
 *
 * Split out of the component for the same reason `trajectory.ts` was: these are
 * plain functions the `lib` jest project can assert directly, and the ones the
 * renderer calls per frame carry the `"worklet"` directive so they can run on
 * the UI thread.
 *
 * Nothing here does physics. The server sends every body as a sampled path in
 * world units and the index is the clock, exactly as the trajectory graph
 * does — this file only maps those samples onto the screen and reads
 * directions off them.
 */

export type SimulationArrow = "gravity" | "velocity" | "centripetal";

export type SimulationBody = {
  label?: string;
  radius: number;
  /** [x, y] world-unit samples, uniform in time. */
  path: number[][];
  role: "primary" | "secondary";
};

export type SimulationSpec = {
  type: "projectile_motion" | "orbit";
  title?: string;
  bodies: SimulationBody[];
  xMin: number;
  xMax: number;
  yMin: number;
  yMax: number;
  arrows: SimulationArrow[];
  centre?: { x: number; y: number };
  ground: boolean;
};

const MAX_BODIES = 4;
const MAX_PATH_POINTS = 500;
const ARROW_KINDS: readonly SimulationArrow[] = ["gravity", "velocity", "centripetal"];

/**
 * Strictly a JSON number — no coercion.
 *
 * `Number(null)` and `Number("")` are both 0, so a coercing reader accepts a
 * missing coordinate as the origin and quietly draws the body somewhere it
 * never was. The server always sends numbers, so nothing is lost by refusing
 * everything else.
 */
function finite(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function parsePath(raw: unknown): number[][] | null {
  if (!Array.isArray(raw) || raw.length < 2 || raw.length > MAX_PATH_POINTS) return null;
  const out: number[][] = [];
  for (const pair of raw) {
    if (!Array.isArray(pair) || pair.length !== 2) return null;
    const x = finite(pair[0]);
    const y = finite(pair[1]);
    if (x === null || y === null) return null;
    out.push([x, y]);
  }
  return out;
}

function parseBody(raw: unknown): SimulationBody | null {
  if (!raw || typeof raw !== "object") return null;
  const row = raw as Record<string, unknown>;
  const path = parsePath(row.path);
  if (!path) return null;
  const radius = finite(row.radius);
  return {
    label: typeof row.label === "string" && row.label ? row.label.slice(0, 32) : undefined,
    // A non-positive radius would draw nothing at all, so it falls back rather
    // than rendering an invisible body.
    radius: radius !== null && radius > 0 ? radius : 0.4,
    path,
    role: row.role === "secondary" ? "secondary" : "primary",
  };
}

/**
 * Read a scene, or return null so the block can show its fallback.
 *
 * Deliberately as strict as the server model: this fence is server-owned, so
 * anything that does not parse is a bug or an invention, and neither should
 * reach the screen as a half-drawn animation.
 */
export function parseSimulationSpec(raw: string): SimulationSpec | null {
  let data: unknown;
  try {
    data = JSON.parse(raw.trim());
  } catch {
    return null;
  }
  if (!data || typeof data !== "object") return null;
  const row = data as Record<string, unknown>;
  if (row.type !== "projectile_motion" && row.type !== "orbit") return null;

  const rawBodies = Array.isArray(row.bodies) ? row.bodies : [];
  if (rawBodies.length === 0 || rawBodies.length > MAX_BODIES) return null;
  const bodies: SimulationBody[] = [];
  for (const entry of rawBodies) {
    const body = parseBody(entry);
    if (!body) return null;
    bodies.push(body);
  }
  // One clock drives every body, so unequal sample counts would put a
  // two-body scene out of step — a collision shown at the wrong moment.
  if (new Set(bodies.map((b) => b.path.length)).size > 1) return null;

  const xMin = finite(row.x_min);
  const xMax = finite(row.x_max);
  const yMin = finite(row.y_min);
  const yMax = finite(row.y_max);
  if (xMin === null || xMax === null || yMin === null || yMax === null) return null;
  if (xMax <= xMin || yMax <= yMin) return null;

  const arrows = Array.isArray(row.arrows)
    ? (row.arrows.filter((a) => ARROW_KINDS.includes(a as SimulationArrow)) as SimulationArrow[])
    : [];

  let centre: { x: number; y: number } | undefined;
  if (Array.isArray(row.centre) && row.centre.length === 2) {
    const cx = finite(row.centre[0]);
    const cy = finite(row.centre[1]);
    if (cx !== null && cy !== null) centre = { x: cx, y: cy };
  }
  // "Toward the centre" needs a centre; drawing it from nowhere would point
  // the arrow at the origin of the scene box instead.
  const usable = centre ? arrows : arrows.filter((a) => a !== "centripetal");

  return {
    type: row.type,
    title: typeof row.title === "string" && row.title ? row.title.slice(0, 64) : undefined,
    bodies,
    xMin,
    xMax,
    yMin,
    yMax,
    arrows: usable,
    centre,
    ground: row.ground === true,
  };
}

export type SimulationTransform = {
  scale: number;
  offsetX: number;
  offsetY: number;
  height: number;
};

/**
 * World units to screen pixels, with **one** scale for both axes.
 *
 * Stretching each axis to fill the box is what a graph does, and it would be
 * wrong here: an orbit would come out an ellipse, and a projectile's launch
 * angle would not be the angle it was launched at. The scene is letterboxed
 * into the box instead, and centred in whichever direction has slack.
 */
export function simulationTransform(
  spec: SimulationSpec,
  width: number,
  height: number,
  pad: number,
): SimulationTransform {
  const innerW = Math.max(width - pad * 2, 1);
  const innerH = Math.max(height - pad * 2, 1);
  const worldW = spec.xMax - spec.xMin;
  const worldH = spec.yMax - spec.yMin;
  const scale = Math.min(innerW / worldW, innerH / worldH);
  return {
    scale,
    offsetX: pad + (innerW - worldW * scale) / 2 - spec.xMin * scale,
    // y grows upward in the world and downward on screen, so the offset is
    // measured from the bottom of the letterboxed area.
    offsetY: pad + innerH - (innerH - worldH * scale) / 2 + spec.yMin * scale,
    height,
  };
}

export type ScreenPoint = { px: number; py: number };

export function worldToScreen(x: number, y: number, t: SimulationTransform): ScreenPoint {
  "worklet";
  return { px: x * t.scale + t.offsetX, py: t.offsetY - y * t.scale };
}

/** Screen-space samples, mapped once so the worklet only ever indexes. */
export function projectPath(path: number[][], t: SimulationTransform): ScreenPoint[] {
  return path.map(([x, y]) => worldToScreen(x, y, t));
}

export function polylinePoints(points: readonly ScreenPoint[]): string {
  return points.map((p) => `${p.px.toFixed(2)},${p.py.toFixed(2)}`).join(" ");
}

/**
 * The arrow as one 5-point polyline: tail → tip → one head barb → tip → the
 * other.
 *
 * `TrajectoryChart` warns against building point strings in a worklet, and it
 * is right about a 100-point curve rebuilt every frame. Five points is a
 * different order of magnitude, and the alternative — a separate animated
 * `Polygon` head whose position has to be kept in step with an animated
 * `Line` — is more moving parts for a worse result.
 */
export function arrowPolyline(
  from: ScreenPoint,
  dx: number,
  dy: number,
  length: number,
  head: number,
): string {
  "worklet";
  const len = Math.hypot(dx, dy) || 1;
  const ux = dx / len;
  const uy = dy / len;
  const tipX = from.px + ux * length;
  const tipY = from.py + uy * length;
  // Perpendicular, for the two barbs.
  const bx = uy * head * 0.6;
  const by = ux * head * 0.6;
  const leftX = tipX - ux * head + bx;
  const leftY = tipY - uy * head - by;
  const rightX = tipX - ux * head - bx;
  const rightY = tipY - uy * head + by;
  return (
    `${from.px.toFixed(2)},${from.py.toFixed(2)} ${tipX.toFixed(2)},${tipY.toFixed(2)} ` +
    `${leftX.toFixed(2)},${leftY.toFixed(2)} ${tipX.toFixed(2)},${tipY.toFixed(2)} ` +
    `${rightX.toFixed(2)},${rightY.toFixed(2)}`
  );
}

/**
 * Direction of travel at `progress`, read from the neighbouring samples.
 *
 * Taken across a small window rather than between adjacent points: on a
 * densely sampled path two neighbours can round to the same pixel, and a
 * zero-length tangent makes the velocity arrow flip about randomly.
 */
export function tangentAt(points: readonly ScreenPoint[], progress: number): { dx: number; dy: number } {
  "worklet";
  const last = points.length - 1;
  if (last < 1) return { dx: 1, dy: 0 };
  const clamped = progress < 0 ? 0 : progress > 1 ? 1 : progress;
  const window = Math.max(1, Math.round(last * 0.04));
  const at = Math.round(clamped * last);
  const lo = at - window < 0 ? 0 : at - window;
  const hi = at + window > last ? last : at + window;
  const a = points[lo];
  const b = points[hi];
  const dx = b.px - a.px;
  const dy = b.py - a.py;
  if (dx === 0 && dy === 0) return { dx: 1, dy: 0 };
  return { dx, dy };
}
