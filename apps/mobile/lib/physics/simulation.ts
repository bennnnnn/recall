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
  | "vector_sum"
  | "spring";

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
  /**
   * How long these are on screen depends on the scene (`vectorScreenLengths`):
   * a vector-sum part or a `measure` is drawn at its true world length, and
   * every other vector is only *relative* — its direction, and a magnitude
   * compared with the other vectors of its kind in the same scene.
   */
  dx: number;
  dy: number;
  label?: string;
  /**
   * Visual weight only. `result` is the quantity the question asked for;
   * `measure` is an extent rather than a force — the h in mgh, the d in Fd —
   * drawn as a dimension line so it does not read as another arrow pushing;
   * `motion` is a kinematic arrow (an acceleration), drawn dashed with an
   * open head so it never reads as a force.
   */
  role: SimulationVectorRole;
};

export type SimulationVectorRole = "force" | "result" | "measure" | "motion";

const VECTOR_ROLES: readonly SimulationVectorRole[] = ["force", "result", "measure", "motion"];

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
  /** Fixed end of a spring, in world coords. The coil is drawn from here. */
  anchor?: { x: number; y: number };
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
  "spring",
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
    // An unknown role is drawn as a plain force: the arrow still says
    // something true about direction, and a newer server never blanks a scene.
    role: VECTOR_ROLES.includes(row.role as SimulationVectorRole)
      ? (row.role as SimulationVectorRole)
      : "force",
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
  let anchor: { x: number; y: number } | undefined;
  if (Array.isArray(row.anchor) && row.anchor.length === 2) {
    const ax = finite(row.anchor[0]);
    const ay = finite(row.anchor[1]);
    if (ax !== null && ay !== null) anchor = { x: ax, y: ay };
  }
  // A spring with no wall would start the coil at the canvas edge, which is
  // not the spring the solver sampled.
  if (row.type === "spring" && (anchor === undefined || bodies.length !== 1)) return null;

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
    anchor,
  };
}

/** Padding inside the scene canvas, around the scene box. */
export const SIMULATION_PAD = 24;
/** Tallest a scene canvas grows (square and tall scenes). */
export const SIMULATION_HEIGHT = 240;
/** Shortest a scene canvas shrinks (wide scenes). */
export const SIMULATION_MIN_HEIGHT = 136;

/** Whether any body moves, i.e. whether the scene has anything to play. */
export function simulationIsAnimated(spec: SimulationSpec): boolean {
  return spec.bodies.some((body) =>
    body.path.some((point) => point[0] !== body.path[0][0] || point[1] !== body.path[0][1]),
  );
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

/**
 * Whether a sampled path is a loop the clock goes round: it ends where it
 * started *and* carries straight on through that join.
 *
 * Both halves matter. An orbit, or a spring sampled over whole periods, ends
 * on its first sample still travelling the same way, so the motion at t = 1
 * is the motion at t = 0. A ball thrown straight up and caught also ends where
 * it started, but arrives moving the opposite way — wrapping that path would
 * average the throw with the catch and draw no velocity at all at launch.
 */
export function isClosedPath(points: readonly ScreenPoint[]): boolean {
  const last = points.length - 1;
  if (last < 3) return false;
  const first = points[0];
  const end = points[last];
  let extent = 0;
  for (const p of points) extent = Math.max(extent, Math.hypot(p.px - first.px, p.py - first.py));
  if (extent === 0) return false;
  if (Math.hypot(end.px - first.px, end.py - first.py) > Math.max(0.5, extent * 0.01)) {
    return false;
  }
  const outX = points[1].px - first.px;
  const outY = points[1].py - first.py;
  const inX = end.px - points[last - 1].px;
  const inY = end.py - points[last - 1].py;
  const outLength = Math.hypot(outX, outY);
  const inLength = Math.hypot(inX, inY);
  if (outLength === 0 || inLength === 0) return false;
  // Coarse loops turn by 360°/n per sample, so a square still counts; a path
  // that doubles back (≥ 120°) does not.
  return (outX * inX + outY * inY) / (outLength * inLength) > -0.5;
}

/**
 * The path at a fractional sample index in [0, last], linearly interpolated.
 *
 * Declared before `tangentAt` on purpose: a worklet captures the functions it
 * calls when it is defined, so a helper declared below it is `undefined` on
 * the UI thread.
 */
function samplePathAt(points: readonly ScreenPoint[], index: number): ScreenPoint {
  "worklet";
  const last = points.length - 1;
  const lo = Math.floor(index);
  const hi = lo + 1 > last ? last : lo + 1;
  const frac = index - lo;
  return {
    px: points[lo].px + (points[hi].px - points[lo].px) * frac,
    py: points[lo].py + (points[hi].py - points[lo].py) * frac,
  };
}

/**
 * Velocity at `progress`, as screen pixels per sample.
 *
 * Taken across a small window rather than between adjacent points: on a
 * densely sampled path two neighbours can round to the same pixel, and a
 * near-zero tangent makes the velocity arrow flip about randomly. The window
 * is what solves that, so a genuinely zero result here means the body is not
 * moving — which collisions and held blocks both produce — and it is returned
 * as zero rather than papered over with a default direction that would draw a
 * velocity arrow on a stationary ball.
 *
 * The samples are uniform in time, so dividing by the window's span makes the
 * length proportional to speed with no physics repeated here — including at
 * the ends, where the window is cut in half. On a closed path
 * (`isClosedPath`) the window wraps round the join instead, so an orbit's
 * arrow is as tangent at t = 0 and t = 1 as anywhere else.
 */
export function tangentAt(
  points: readonly ScreenPoint[],
  progress: number,
  closed = false,
): { dx: number; dy: number } {
  "worklet";
  const last = points.length - 1;
  if (last < 1) return { dx: 0, dy: 0 };
  const clamped = progress < 0 ? 0 : progress > 1 ? 1 : progress;
  const window = Math.max(1, Math.round(last * 0.04));
  // Read at the fractional index the body is drawn at, so the arrow turns
  // smoothly with it instead of snapping from sample to sample.
  const at = clamped * last;
  const wraps = closed && last > 2 * window;
  let lo = at - window;
  let hi = at + window;
  if (wraps) {
    // The last sample repeats the first, so the loop has `last` distinct ones.
    if (lo < 0) lo += last;
    if (hi > last) hi -= last;
  } else {
    lo = lo < 0 ? 0 : lo;
    hi = hi > last ? last : hi;
  }
  const span = wraps ? 2 * window : hi - lo;
  if (span <= 0) return { dx: 0, dy: 0 };
  const a = samplePathAt(points, lo);
  const b = samplePathAt(points, hi);
  return { dx: (b.px - a.px) / span, dy: (b.py - a.py) / span };
}

/** The fastest the body moves anywhere on its path, in `tangentAt`'s units. */
export function maxTrackSpeed(points: readonly ScreenPoint[], closed = false): number {
  const last = points.length - 1;
  let best = 0;
  for (let i = 0; i <= last; i += 1) {
    const v = tangentAt(points, last > 0 ? i / last : 0, closed);
    best = Math.max(best, Math.hypot(v.dx, v.dy));
  }
  return best;
}

/**
 * Longest a relative arrow is drawn. Every non-measure vector in a scene is
 * scaled so its largest is this long, and velocity at top speed is too.
 */
export const ARROW_MAX_LENGTH = 48;
/** Shortest a relative force arrow is drawn, so a small load is still an arrow. */
export const ARROW_MIN_LENGTH = 16;
/** Shortest a moving body's velocity arrow is drawn. */
export const VELOCITY_MIN_LENGTH = 12;
export const ARROW_HEAD = 7;
/** Room kept between an arrow's tip and the canvas edge, so its head stays in. */
export const ARROW_EDGE_INSET = 6;

/**
 * Velocity arrow length from speed alone: proportional to how fast the body
 * is moving now against the fastest any body moves in the scene, so the apex
 * of a throw is visibly slower than the launch and the lighter ball visibly
 * faster after a collision. Zero speed draws nothing.
 */
export function velocityArrowLength(speed: number, maxSpeed: number): number {
  "worklet";
  if (!(speed > 0) || !(maxSpeed > 0)) return 0;
  const length = (ARROW_MAX_LENGTH * speed) / maxSpeed;
  return length < VELOCITY_MIN_LENGTH
    ? VELOCITY_MIN_LENGTH
    : length > ARROW_MAX_LENGTH
      ? ARROW_MAX_LENGTH
      : length;
}

/** A vector the scene states at its true world length. */
export function drawsAtWorldScale(spec: SimulationSpec, vector: SimulationVector): boolean {
  return spec.type === "vector_sum" || vector.role === "measure";
}

/**
 * On-screen length of each stated vector, in the order the scene lists them.
 *
 * A vector-sum part and a `measure` are geometry, so they keep their world
 * length exactly — a 2 N component next to a 100 N one is meant to be tiny.
 * Everything else is relative: the longest of its kind is drawn at
 * `ARROW_MAX_LENGTH` and the rest in proportion, never shorter than
 * `ARROW_MIN_LENGTH`. Forces and `motion` arrows are normalised separately,
 * since newtons and m/s² share no scale. An old server sent unit vectors,
 * which all come out at the maximum length.
 */
export function vectorScreenLengths(spec: SimulationSpec, scale: number): number[] {
  const largest = { force: 0, motion: 0 };
  for (const vector of spec.vectors) {
    if (drawsAtWorldScale(spec, vector)) continue;
    const family = vector.role === "motion" ? "motion" : "force";
    largest[family] = Math.max(largest[family], Math.hypot(vector.dx, vector.dy));
  }
  return spec.vectors.map((vector) => {
    const magnitude = Math.hypot(vector.dx, vector.dy);
    if (drawsAtWorldScale(spec, vector)) return magnitude * scale;
    const max = largest[vector.role === "motion" ? "motion" : "force"];
    if (!(max > 0) || magnitude >= max) return ARROW_MAX_LENGTH;
    return Math.max(ARROW_MIN_LENGTH, ARROW_MAX_LENGTH * (magnitude / max));
  });
}

/**
 * The longest an arrow from (`fromX`, `fromY`) along the unit direction
 * (`ux`, `uy`) can be while its tip stays `inset` inside the canvas — at most
 * `length`. An arrow that leaves the canvas loses its head, and a headless
 * line reads as nothing at all.
 */
export function fitArrowLength(
  fromX: number,
  fromY: number,
  ux: number,
  uy: number,
  length: number,
  width: number,
  height: number,
  inset = ARROW_EDGE_INSET,
): number {
  "worklet";
  let fit = length;
  if (ux > 1e-9) fit = Math.min(fit, (width - inset - fromX) / ux);
  else if (ux < -1e-9) fit = Math.min(fit, (inset - fromX) / ux);
  if (uy > 1e-9) fit = Math.min(fit, (height - inset - fromY) / uy);
  else if (uy < -1e-9) fit = Math.min(fit, (inset - fromY) / uy);
  return fit > 0 ? fit : 0;
}

/** A head never longer than about half its arrow. */
export function arrowHeadSize(length: number): number {
  "worklet";
  return Math.min(ARROW_HEAD, length * 0.45);
}

/**
 * Where an arrow the scene derives (rather than states) is drawn this frame:
 * from the body's edge, along a direction read off the scene, shortened to
 * stay on the canvas. Null when there is nothing to draw — a ball at rest has
 * no velocity, and an arrow toward a centre the body sits on has no direction.
 *
 * Velocity is as long as the body is fast (`velocityArrowLength`); the force
 * arrows have no magnitude to show, so they share one length.
 */
export function derivedArrowGeometry(
  kind: SimulationArrow,
  at: ScreenPoint,
  radius: number,
  context: {
    tangent: { dx: number; dy: number };
    maxSpeed: number;
    centre: ScreenPoint | null;
    slope: { normal: { dx: number; dy: number }; friction: { dx: number; dy: number } } | null;
    width: number;
    height: number;
  },
): { fromX: number; fromY: number; ux: number; uy: number; length: number } | null {
  "worklet";
  let dx = 0;
  let dy = 0;
  let length = ARROW_MAX_LENGTH;
  if (kind === "gravity") {
    dy = 1;
  } else if (kind === "velocity") {
    dx = context.tangent.dx;
    dy = context.tangent.dy;
    length = velocityArrowLength(Math.hypot(dx, dy), context.maxSpeed);
  } else if (kind === "centripetal" && context.centre) {
    dx = context.centre.px - at.px;
    dy = context.centre.py - at.py;
    // Never past the centre it points at.
    length = Math.min(length, Math.hypot(dx, dy) - radius - 2);
  } else if (kind === "normal" && context.slope) {
    dx = context.slope.normal.dx;
    dy = context.slope.normal.dy;
  } else if (kind === "friction" && context.slope) {
    dx = context.slope.friction.dx;
    dy = context.slope.friction.dy;
  }
  const magnitude = Math.hypot(dx, dy);
  if (magnitude === 0 || !(length > 0)) return null;
  const ux = dx / magnitude;
  const uy = dy / magnitude;
  const fromX = at.px + ux * radius;
  const fromY = at.py + uy * radius;
  const fit = fitArrowLength(fromX, fromY, ux, uy, length, context.width, context.height);
  if (!(fit > 0)) return null;
  return { fromX, fromY, ux, uy, length: fit };
}

/** The fulcrum wedge under a lever's pivot: half-width, and height below the beam. */
export const PIVOT_SIZE = 7;
/** Clear space kept between a load arrow and the wedge. */
const LEVER_PIVOT_GAP = 6;

/**
 * Where a lever load's arrow starts, kept clear of the fulcrum wedge.
 *
 * A load 0.1 m from the pivot sits on the wedge, and the shaft plus the
 * triangle read as a double-headed arrow. A downward load that close is moved
 * just far enough sideways to clear the wedge; its label still states the
 * real arm.
 */
export function leverLoadAnchor(
  from: ScreenPoint,
  uy: number,
  pivot: ScreenPoint,
): ScreenPoint {
  if (uy <= 0) return from;
  const clear = PIVOT_SIZE + LEVER_PIVOT_GAP;
  const offset = from.px - pivot.px;
  if (Math.abs(offset) >= clear) return from;
  return { px: pivot.px + (offset < 0 ? -clear : clear), py: from.py };
}

// --- labels ------------------------------------------------------------------

/** A label's box: left, top, width and height in canvas pixels. */
export type LabelBox = { x: number; y: number; width: number; height: number };

/** Gap between a label and the thing it names. */
export const LABEL_GAP = 6;
/** Skia text is drawn from its baseline, about this far down a line. */
const LABEL_ASCENT = 0.8;

/** The baseline Skia draws a label at, for a box from `vectorLabelBox`. */
export function labelBaseline(box: LabelBox): number {
  return box.y + box.height * LABEL_ASCENT;
}

function boxesOverlap(a: LabelBox, b: LabelBox, gap = 0): boolean {
  return (
    a.x < b.x + b.width + gap &&
    b.x < a.x + a.width + gap &&
    a.y < b.y + b.height + gap &&
    b.y < a.y + a.height + gap
  );
}

function clampBox(box: LabelBox, width: number, height: number, inset = 4): LabelBox {
  const x = Math.max(inset, Math.min(width - inset - box.width, box.x));
  const y = Math.max(inset, Math.min(height - inset - box.height, box.y));
  return { ...box, x, y };
}

export type Segment = { x1: number; y1: number; x2: number; y2: number };

/** Whether a line segment passes through a box (Liang–Barsky clip). */
export function segmentHitsBox(segment: Segment, box: LabelBox): boolean {
  const dx = segment.x2 - segment.x1;
  const dy = segment.y2 - segment.y1;
  let t0 = 0;
  let t1 = 1;
  const edges: [number, number][] = [
    [-dx, segment.x1 - box.x],
    [dx, box.x + box.width - segment.x1],
    [-dy, segment.y1 - box.y],
    [dy, box.y + box.height - segment.y1],
  ];
  for (const [p, q] of edges) {
    if (p === 0) {
      if (q < 0) return false;
      continue;
    }
    const r = q / p;
    if (p < 0) t0 = Math.max(t0, r);
    else t1 = Math.min(t1, r);
    if (t0 > t1) return false;
  }
  return true;
}

/** Room kept between a label and another arrow's line, in px. */
const LINE_CLEARANCE = 4;

function inflateBox(box: LabelBox, by: number): LabelBox {
  return { x: box.x - by, y: box.y - by, width: box.width + by * 2, height: box.height + by * 2 };
}

/** Furthest a label is nudged from where it wants to be, in px. */
const MAX_NUDGE = 48;
const NUDGE_STEP = 2;

/**
 * Nudge labels apart, in priority order: each box keeps its place unless it
 * overlaps a `fixed` box, one placed before it, or a line in its `avoid` list
 * (the other arrows' shafts), and then moves the shortest way out — straight
 * along one axis — that stays on the canvas and is clear of all three.
 */
export function separateLabels(
  boxes: readonly LabelBox[],
  fixed: readonly LabelBox[],
  width: number,
  height: number,
  avoid: readonly (readonly Segment[])[] = [],
  gap = 2,
): LabelBox[] {
  const placed: LabelBox[] = [...fixed];
  return boxes.map((start, index) => {
    const lines = avoid[index] ?? [];
    // Lines keep a little more room than labels do: the halo is drawn
    // outside the glyphs, and a line grazing it reads as a strike-through.
    const clear = (box: LabelBox) =>
      !placed.some((other) => boxesOverlap(box, other, gap)) &&
      !lines.some((line) => segmentHitsBox(line, inflateBox(box, LINE_CLEARANCE)));
    const home = clampBox(start, width, height);
    let box = home;
    if (!clear(home)) {
      search: for (let step = NUDGE_STEP; step <= MAX_NUDGE; step += NUDGE_STEP) {
        for (const [dx, dy] of [
          [0, step],
          [0, -step],
          [step, 0],
          [-step, 0],
        ]) {
          const candidate = clampBox({ ...home, x: home.x + dx, y: home.y + dy }, width, height);
          if (clear(candidate)) {
            box = candidate;
            break search;
          }
        }
      }
    }
    placed.push(box);
    return box;
  });
}

export type BodyLabelSide = "above" | "below" | "right" | "left";

/**
 * Where a body's label box sits relative to the body's centre (its top-left
 * corner, as an offset). Above and below are centred on the body, so two
 * balls side by side never print "2 kg1 kg" across each other.
 */
export function bodyLabelOffset(
  side: BodyLabelSide,
  radius: number,
  labelWidth: number,
  fontSize: number,
): { dx: number; dy: number } {
  "worklet";
  const ascent = fontSize * LABEL_ASCENT;
  switch (side) {
    case "below":
      return { dx: -labelWidth / 2, dy: radius + LABEL_GAP };
    case "right":
      return { dx: radius + LABEL_GAP, dy: -fontSize / 2 };
    case "left":
      return { dx: -(radius + LABEL_GAP + labelWidth), dy: -fontSize / 2 };
    default:
      // Baseline `LABEL_GAP` above the top of the body.
      return { dx: -labelWidth / 2, dy: -(radius + LABEL_GAP) - ascent };
  }
}

/**
 * The first side, in the body's order of preference, where its label crosses
 * no arrow and fits on the canvas. The primary body prefers above and a
 * secondary body below, so a pair of bodies never shares a label line.
 */
export function chooseBodyLabelSide(
  centre: ScreenPoint,
  radius: number,
  labelWidth: number,
  fontSize: number,
  role: SimulationBody["role"],
  obstacles: readonly Segment[],
  width: number,
  height: number,
): BodyLabelSide {
  const order: BodyLabelSide[] =
    role === "secondary" ? ["below", "above", "right", "left"] : ["above", "below", "right", "left"];
  const fits = (side: BodyLabelSide) => {
    const offset = bodyLabelOffset(side, radius, labelWidth, fontSize);
    const box = {
      x: centre.px + offset.dx - 1,
      y: centre.py + offset.dy - 1,
      width: labelWidth + 2,
      height: fontSize + 2,
    };
    const inside = box.x >= 0 && box.y >= 0 && box.x + box.width <= width && box.y + box.height <= height;
    return inside && !obstacles.some((segment) => segmentHitsBox(segment, box));
  };
  return order.find(fits) ?? order[0];
}

/**
 * A stated vector's label box. `tip` puts it just past the arrowhead, centred
 * on the line of the arrow; `mid` puts it beside the middle of the shaft, on
 * `side` (+1 or −1) of it — which is how a component and a dimension line are
 * labelled, so a component never shares the result's tip.
 */
export function vectorLabelBox(
  from: ScreenPoint,
  tip: ScreenPoint,
  labelWidth: number,
  fontSize: number,
  mode: "tip" | "mid",
  side: 1 | -1 = 1,
): LabelBox {
  const dx = tip.px - from.px;
  const dy = tip.py - from.py;
  const length = Math.hypot(dx, dy) || 1;
  const ux = dx / length;
  const uy = dy / length;
  const reach = (nx: number, ny: number) =>
    LABEL_GAP + (Math.abs(nx) * labelWidth) / 2 + (Math.abs(ny) * fontSize) / 2;
  let cx: number;
  let cy: number;
  if (mode === "tip") {
    const r = reach(ux, uy);
    cx = tip.px + ux * r;
    cy = tip.py + uy * r;
  } else {
    const nx = -uy * side;
    const ny = ux * side;
    const r = reach(nx, ny);
    cx = (from.px + tip.px) / 2 + nx * r;
    cy = (from.py + tip.py) / 2 + ny * r;
  }
  return { x: cx - labelWidth / 2, y: cy - fontSize / 2, width: labelWidth, height: fontSize };
}

/** How a stated vector is drawn. */
export type VectorStroke = "force" | "motion" | "measure";

export function vectorStroke(role: SimulationVectorRole): VectorStroke {
  return role === "motion" ? "motion" : role === "measure" ? "measure" : "force";
}

export type VectorLayout = {
  vector: SimulationVector;
  from: ScreenPoint;
  tip: ScreenPoint;
  head: number;
  label: { text: string; x: number; y: number; box: LabelBox } | null;
};

export type BodyLabelLayout = {
  side: BodyLabelSide;
  /** Offset from the body's centre to the label's left edge and baseline. */
  dx: number;
  dy: number;
  width: number;
};

export type SceneLayout = {
  radii: number[];
  vectors: VectorLayout[];
  bodyLabels: (BodyLabelLayout | null)[];
};

/** The smallest a body is drawn, so a 2 cm ball is still a dot. */
export const MIN_BODY_RADIUS = 4;

function unit(dx: number, dy: number): { ux: number; uy: number } {
  const length = Math.hypot(dx, dy) || 1;
  return { ux: dx / length, uy: dy / length };
}

function isStationary(body: SimulationBody): boolean {
  const [x0, y0] = body.path[0];
  return body.path.every(([x, y]) => x === x0 && y === y0);
}

/**
 * Every static piece of a scene's layout, worked out once per size: stated
 * vectors with their lengths, canvas fit and labels, and which side of each
 * body its label goes.
 *
 * `measureText` is the font's width for a string. The body labels are
 * offsets, since the body moves; the vector labels are placed outright and
 * nudged off each other and off any still body's label.
 */
export function layoutSimulationScene(
  spec: SimulationSpec,
  transform: SimulationTransform,
  width: number,
  height: number,
  measureText: (text: string) => number,
  fontSize: number,
): SceneLayout {
  const radii = spec.bodies.map((body) => Math.max(body.radius * transform.scale, MIN_BODY_RADIUS));
  const pivot = spec.pivot && spec.beam ? worldToScreen(spec.pivot.x, spec.pivot.y, transform) : null;
  const lengths = vectorScreenLengths(spec, transform.scale);

  // A body is drawn over the arrows that start at its centre, so an arrow
  // anchored on a still body starts at its edge instead: the part you see is
  // then the whole length, and two forces keep their proportions.
  const stillBodies = spec.bodies.flatMap((body, index) =>
    isStationary(body)
      ? [{ centre: worldToScreen(body.path[0][0], body.path[0][1], transform), radius: radii[index] }]
      : [],
  );

  const shafts = spec.vectors.map((vector, index) => {
    // World y is up and screen y is down.
    const { ux, uy } = unit(vector.dx, -vector.dy);
    let from = worldToScreen(vector.anchor.x, vector.anchor.y, transform);
    if (pivot) from = leverLoadAnchor(from, uy, pivot);
    const body = stillBodies.find(
      ({ centre }) => Math.hypot(centre.px - from.px, centre.py - from.py) < 0.5,
    );
    if (body) from = { px: from.px + ux * body.radius, py: from.py + uy * body.radius };
    const length = fitArrowLength(from.px, from.py, ux, uy, lengths[index], width, height);
    const tip = { px: from.px + ux * length, py: from.py + uy * length };
    return { vector, from, tip, head: arrowHeadSize(length) };
  });
  const segments: Segment[] = shafts.map(({ from, tip }) => ({
    x1: from.px,
    y1: from.py,
    x2: tip.px,
    y2: tip.py,
  }));

  // Derived arrows whose direction never changes, at a body's first sample.
  const slope = spec.inclineDeg !== undefined ? inclineDirections(spec.inclineDeg) : null;
  const fixedDirections: { dx: number; dy: number }[] = [];
  if (spec.arrows.includes("gravity")) fixedDirections.push({ dx: 0, dy: 1 });
  if (slope && spec.arrows.includes("normal")) fixedDirections.push(slope.normal);
  if (slope && spec.arrows.includes("friction")) fixedDirections.push(slope.friction);

  const fixedBoxes: LabelBox[] = [];
  const bodyLabels = spec.bodies.map((body, index) => {
    const radius = radii[index];
    const start = worldToScreen(body.path[0][0], body.path[0][1], transform);
    const still = isStationary(body);
    if (still) {
      fixedBoxes.push({
        x: start.px - radius,
        y: start.py - radius,
        width: radius * 2,
        height: radius * 2,
      });
    }
    if (!body.label) return null;
    const labelWidth = measureText(body.label);
    const derived = fixedDirections.map(({ dx, dy }) => {
      const { ux, uy } = unit(dx, dy);
      const fromX = start.px + ux * radius;
      const fromY = start.py + uy * radius;
      const length = fitArrowLength(fromX, fromY, ux, uy, ARROW_MAX_LENGTH, width, height);
      return { x1: fromX, y1: fromY, x2: fromX + ux * length, y2: fromY + uy * length };
    });
    const side = chooseBodyLabelSide(
      start,
      radius,
      labelWidth,
      fontSize,
      body.role,
      [...segments, ...derived],
      width,
      height,
    );
    const offset = bodyLabelOffset(side, radius, labelWidth, fontSize);
    if (still) {
      fixedBoxes.push({
        x: start.px + offset.dx,
        y: start.py + offset.dy,
        width: labelWidth,
        height: fontSize,
      });
    }
    return {
      side,
      dx: offset.dx,
      dy: offset.dy + fontSize * LABEL_ASCENT,
      width: labelWidth,
    };
  });

  // The middle of the figure, so a side label goes outward rather than into
  // the triangle the vectors make.
  let sumX = 0;
  let sumY = 0;
  let count = 0;
  for (const { from, tip } of shafts) {
    sumX += from.px + tip.px;
    sumY += from.py + tip.py;
    count += 2;
  }
  for (const body of spec.bodies) {
    const start = worldToScreen(body.path[0][0], body.path[0][1], transform);
    sumX += start.px;
    sumY += start.py;
    count += 1;
  }
  const centroid = count > 0 ? { px: sumX / count, py: sumY / count } : { px: width / 2, py: height / 2 };

  const wanted = shafts.map(({ vector, from, tip }) => {
    if (!vector.label) return null;
    const labelWidth = measureText(vector.label);
    const beside =
      vector.role === "measure" || (spec.type === "vector_sum" && vector.role !== "result");
    if (!beside) return vectorLabelBox(from, tip, labelWidth, fontSize, "tip");
    const { ux, uy } = unit(tip.px - from.px, tip.py - from.py);
    const midX = (from.px + tip.px) / 2 - centroid.px;
    const midY = (from.py + tip.py) / 2 - centroid.py;
    const side = -uy * midX + ux * midY >= 0 ? 1 : -1;
    return vectorLabelBox(from, tip, labelWidth, fontSize, "mid", side);
  });
  // The answer keeps its place; everything else moves out of its way.
  const order = wanted
    .map((box, index) => ({ box, index }))
    .filter((entry): entry is { box: LabelBox; index: number } => entry.box !== null)
    .sort(
      (a, b) =>
        Number(spec.vectors[b.index].role === "result") -
        Number(spec.vectors[a.index].role === "result"),
    );
  // A label may sit on its own arrow's line of action, never across another.
  const separated = separateLabels(
    order.map((entry) => entry.box),
    fixedBoxes,
    width,
    height,
    order.map((entry) => segments.filter((_, i) => i !== entry.index)),
  );
  const placedBoxes = new Map(order.map((entry, i) => [entry.index, separated[i]]));

  const vectors = shafts.map((shaft, index): VectorLayout => {
    const box = placedBoxes.get(index);
    return {
      ...shaft,
      label:
        box && shaft.vector.label
          ? { text: shaft.vector.label, x: box.x, y: labelBaseline(box), box }
          : null,
    };
  });

  return { radii, vectors, bodyLabels };
}

// --- description -------------------------------------------------------------

type Translate = (key: string, options?: Record<string, unknown>) => string;

/**
 * What a screen reader hears for the scene: its title, its bodies, the arrows
 * it derives and the labels the solver stated — the same facts the picture
 * shows, in the order a sighted reader takes them in.
 */
export function describeSimulation(spec: SimulationSpec, t: Translate): string {
  const sentences: string[] = [spec.title ?? t("rich.simulation_title")];
  if (spec.bodies.length > 0) {
    sentences.push(
      spec.bodies.map((body) => body.label ?? t("rich.simulation_a11y_body")).join(", "),
    );
  }
  if (spec.inclineDeg !== undefined) {
    sentences.push(t("rich.simulation_a11y_slope", { degrees: Math.round(spec.inclineDeg) }));
  }
  if (spec.arrows.length > 0) {
    const names = spec.arrows.map((arrow) => t(`rich.simulation_arrow_${arrow}`));
    sentences.push(t("rich.simulation_a11y_arrows", { list: names.join(", ") }));
  }
  const labels = spec.vectors.flatMap((vector) => (vector.label ? [vector.label] : []));
  if (labels.length > 0) sentences.push(labels.join(", "));
  return sentences.map((sentence) => sentence.replace(/[.\s]+$/, "")).join(". ") + ".";
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
