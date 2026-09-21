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

export type SimulationArrow =
  | "gravity"
  | "velocity"
  | "centripetal"
  | "normal"
  | "friction";

export type SimulationKind =
  | "projectile_motion"
  | "orbit"
  | "collision"
  | "incline"
  | "lever"
  | "free_body"
  | "vector_sum";

/**
 * An arrow the renderer cannot derive, so the solver states it.
 *
 * Every other arrow comes off the scene — velocity from the tangent,
 * centripetal from the centre, normal and friction from the slope — precisely
 * so it cannot disagree with what is drawn around it. These cannot be: the two
 * loads on a see-saw, the resultant of a 3 N and a 4 N force. The label
 * carries the magnitude the solver already computed, so the picture and the
 * answer pill cannot disagree either.
 */
export type SimulationVector = {
  anchor: { x: number; y: number };
  dx: number;
  dy: number;
  label?: string;
  /**
   * Visual weight only. `result` is the quantity the question asked for;
   * `measure` is an extent rather than a force — the h in mgh, the d in Fd —
   * drawn as a dimension line so it does not read as another arrow pushing.
   */
  role: "force" | "result" | "measure";
};

export type SimulationBody = {
  label?: string;
  radius: number;
  /** [x, y] world-unit samples, uniform in time. */
  path: number[][];
  role: "primary" | "secondary";
};

export type SimulationSpec = {
  type: SimulationKind;
  title?: string;
  bodies: SimulationBody[];
  xMin: number;
  xMax: number;
  yMin: number;
  yMax: number;
  arrows: SimulationArrow[];
  centre?: { x: number; y: number };
  ground: boolean;
  /** Slope in degrees, descending left to right. Fixes normal and friction. */
  inclineDeg?: number;
  vectors: SimulationVector[];
  /** A rigid beam as its two ends, in world coords. */
  beam?: { x1: number; y1: number; x2: number; y2: number };
  pivot?: { x: number; y: number };
};

const MAX_BODIES = 4;
const MAX_PATH_POINTS = 500;
const ARROW_KINDS: readonly SimulationArrow[] = [
  "gravity",
  "velocity",
  "centripetal",
  "normal",
  "friction",
];
const SCENE_KINDS: readonly SimulationKind[] = [
  "projectile_motion",
  "orbit",
  "collision",
  "incline",
  "lever",
  "free_body",
  "vector_sum",
];
const MAX_VECTORS = 6;

function parseVector(raw: unknown): SimulationVector | null {
  if (!raw || typeof raw !== "object") return null;
  const row = raw as Record<string, unknown>;
  const dx = finite(row.dx);
  const dy = finite(row.dy);
  if (dx === null || dy === null || (dx === 0 && dy === 0)) return null;
  if (!Array.isArray(row.anchor) || row.anchor.length !== 2) return null;
  const x = finite(row.anchor[0]);
  const y = finite(row.anchor[1]);
  if (x === null || y === null) return null;
  return {
    anchor: { x, y },
    dx,
    dy,
    label: typeof row.label === "string" && row.label ? row.label.slice(0, 24) : undefined,
    role: row.role === "result" || row.role === "measure" ? row.role : "force",
  };
}

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
  if (!SCENE_KINDS.includes(row.type as SimulationKind)) return null;

  const rawBodies = Array.isArray(row.bodies) ? row.bodies : [];
  if (rawBodies.length > MAX_BODIES) return null;
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
  const rawVectors = Array.isArray(row.vectors) ? row.vectors : [];
  if (rawVectors.length > MAX_VECTORS) return null;
  const vectors: SimulationVector[] = [];
  for (const entry of rawVectors) {
    const vector = parseVector(entry);
    if (!vector) return null;
    vectors.push(vector);
  }
  // A scene with neither is an empty box; one or the other makes it a picture.
  if (bodies.length === 0 && vectors.length === 0) return null;

  let beam: SimulationSpec["beam"];
  if (Array.isArray(row.beam) && row.beam.length === 4) {
    const ends = row.beam.map(finite);
    if (ends.every((v) => v !== null)) {
      beam = { x1: ends[0]!, y1: ends[1]!, x2: ends[2]!, y2: ends[3]! };
    }
  }
  let pivot: { x: number; y: number } | undefined;
  if (beam && Array.isArray(row.pivot) && row.pivot.length === 2) {
    const px = finite(row.pivot[0]);
    const py = finite(row.pivot[1]);
    if (px !== null && py !== null) pivot = { x: px, y: py };
  }

  const inclineDeg = finite(row.incline_deg);

  // Each of these is read off something the scene may not have: "toward the
  // centre" needs a centre, and the normal and friction directions come off
  // the slope rather than the motion — a block that has not started moving has
  // no tangent to read them from. An arrow drawn without its reference points
  // somewhere confidently wrong, which is worse than no arrow.
  const usable = arrows.filter(
    (a) =>
      (a !== "centripetal" || centre !== undefined) &&
      ((a !== "normal" && a !== "friction") || inclineDeg !== null),
  );

  return {
    type: row.type as SimulationKind,
    title: typeof row.title === "string" && row.title ? row.title.slice(0, 64) : undefined,
    bodies,
    xMin,
    xMax,
    yMin,
    yMax,
    arrows: usable,
    centre,
    ground: row.ground === true,
    inclineDeg: inclineDeg ?? undefined,
    vectors,
    beam,
    pivot,
  };
}

export type SimulationTransform = {
  scale: number;
  offsetX: number;
  offsetY: number;
  height: number;
};

/**
 * Size the viewport to the scene instead of vertically centring every scene
 * in a fixed tall box. Wide scenes (projectiles and collisions) therefore sit
 * directly below their title, while square/tall scenes retain the full canvas.
 */
export function simulationViewportHeight(
  spec: SimulationSpec,
  width: number,
  pad: number,
  minHeight: number,
  maxHeight: number,
): number {
  const innerW = Math.max(width - pad * 2, 1);
  const worldW = spec.xMax - spec.xMin;
  const worldH = spec.yMax - spec.yMin;
  const heightAtFullWidth = (worldH / worldW) * innerW + pad * 2;
  return Math.max(minHeight, Math.min(maxHeight, heightAtFullWidth));
}

/** Keep measured canvas text fully inside the drawable viewport. */
export function clampCanvasLabelX(
  desiredX: number,
  labelWidth: number,
  canvasWidth: number,
  inset = 4,
): number {
  "worklet";
  const maxX = Math.max(inset, canvasWidth - inset - Math.max(0, labelWidth));
  return Math.max(inset, Math.min(maxX, desiredX));
}

/** Skia text uses a baseline, so the top also needs one font-height of room. */
export function clampCanvasLabelBaseline(
  desiredY: number,
  fontSize: number,
  canvasHeight: number,
  inset = 4,
): number {
  "worklet";
  const minY = inset + Math.max(0, fontSize);
  const maxY = Math.max(minY, canvasHeight - inset);
  return Math.max(minY, Math.min(maxY, desiredY));
}

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
  const len = Math.hypot(dx, dy);
  // No direction, no arrow. A ball waiting to be hit has no velocity to draw,
  // and an empty points string renders nothing — so the arrow simply appears
  // at the moment of the collision, which is the moment it means something.
  if (len === 0) return "";
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
 * near-zero tangent makes the velocity arrow flip about randomly. The window
 * is what solves that, so a genuinely zero result here means the body is not
 * moving — which collisions and held blocks both produce — and it is returned
 * as zero rather than papered over with a default direction that would draw a
 * velocity arrow on a stationary ball.
 */
export function tangentAt(
  points: readonly ScreenPoint[],
  progress: number,
): { dx: number; dy: number } {
  "worklet";
  const last = points.length - 1;
  if (last < 1) return { dx: 0, dy: 0 };
  const clamped = progress < 0 ? 0 : progress > 1 ? 1 : progress;
  const window = Math.max(1, Math.round(last * 0.04));
  const at = Math.round(clamped * last);
  const lo = at - window < 0 ? 0 : at - window;
  const hi = at + window > last ? last : at + window;
  return { dx: points[hi].px - points[lo].px, dy: points[hi].py - points[lo].py };
}

/**
 * The slope's surface, in screen space, extended across the whole scene.
 *
 * Taken from a point the block actually sits on rather than from the scene
 * box, so the line passes under the block instead of near it. The direction
 * comes from the stated angle, which is the only way a *stationary* block's
 * slope can be known at all.
 */
export function inclineSurface(
  spec: SimulationSpec,
  t: SimulationTransform,
): { x1: number; y1: number; x2: number; y2: number } | null {
  if (spec.inclineDeg === undefined || spec.bodies.length === 0) return null;
  const theta = (spec.inclineDeg * Math.PI) / 180;
  const [bx, by] = spec.bodies[0].path[0];
  // The block's centre sits a radius above the surface it rests on, measured
  // along the normal.
  const r = spec.bodies[0].radius;
  const onSurface = { x: bx - r * Math.sin(theta), y: by - r * Math.cos(theta) };

  const slope = -Math.tan(theta); // world dy per dx, descending to the right
  const left = worldToScreen(spec.xMin, onSurface.y + (spec.xMin - onSurface.x) * slope, t);
  const right = worldToScreen(spec.xMax, onSurface.y + (spec.xMax - onSurface.x) * slope, t);
  return { x1: left.px, y1: left.py, x2: right.px, y2: right.py };
}

/**
 * Screen-space directions fixed by the slope rather than by the motion.
 *
 * Both are perpendicular to each other by construction, so the picture cannot
 * show a normal force that is not normal to the surface it acts on.
 */
export function inclineDirections(inclineDeg: number): {
  normal: { dx: number; dy: number };
  friction: { dx: number; dy: number };
} {
  const theta = (inclineDeg * Math.PI) / 180;
  return {
    // Away from the surface: up and to the right, screen y being downward.
    normal: { dx: Math.sin(theta), dy: -Math.cos(theta) },
    // Up the slope, opposing a block sliding down to the right.
    friction: { dx: -Math.cos(theta), dy: -Math.sin(theta) },
  };
}
