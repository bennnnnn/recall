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
  | "spring"
  | "pendulum";

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
  /**
   * The body this arrow rides on. `anchor` is then an offset from that body's
   * position, every frame: the tension on an Atwood mass goes where it goes.
   */
  body?: number;
};

type SimulationVectorRole = "force" | "result" | "measure" | "motion";

const VECTOR_ROLES: readonly SimulationVectorRole[] = ["force", "result", "measure", "motion"];

type SimulationBodyShape = "circle" | "box";

export type SimulationBody = {
  label?: string;
  radius: number;
  /** [x, y] world-unit samples, uniform in time. */
  path: number[][];
  role: "primary" | "secondary";
  /** A box is a square of side 2 * radius, turned onto the slope of an incline. */
  shape: SimulationBodyShape;
};

/** A taut string from a fixed point to a body: a pendulum, an Atwood rope. */
export type SimulationTether = { anchor: { x: number; y: number }; body: number };

/** The wheel an Atwood machine's rope runs over. */
export type SimulationPulley = { centre: { x: number; y: number }; radius: number };

/** The planet an orbit goes round, drawn at the scene's `centre` at true scale. */
export type SimulationPlanet = { radius: number; label?: string };

/**
 * An arc at a vertex, in degrees counter-clockwise from +x. With `arrow` it is
 * a curved arrow from `startDeg` to `endDeg`: a moment's turning sense.
 */
export type SimulationAngle = {
  vertex: { x: number; y: number };
  startDeg: number;
  endDeg: number;
  label?: string;
  arrow: boolean;
  role: "given" | "result";
};

/** A static rectangle: the table a ball rolls off, a cliff, a tank of water. */
export type SimulationSolid = {
  rect: { xMin: number; yMin: number; xMax: number; yMax: number };
  kind: "solid" | "fluid";
  label?: string;
};

/** Titles the client translates: `rich.scene_title_<key>`. Mirrors the server's `TitleKey`. */
export const SCENE_TITLE_KEYS = [
  "projectile",
  "free_fall",
  "orbit",
  "satellite",
  "circular_motion",
  "collision",
  "recoil",
  "incline",
  "moments",
  "free_body",
  "atwood",
  "forces",
  "spring",
  "pendulum",
  "circuit",
  "lens",
  "mirror",
  "refraction",
  "wave",
  "standing_wave",
  "buoyancy",
  "charges",
] as const;

export type SceneTitleKey = (typeof SCENE_TITLE_KEYS)[number];

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
  tethers: SimulationTether[];
  pulley?: SimulationPulley;
  centralBody?: SimulationPlanet;
  angles: SimulationAngle[];
  solids: SimulationSolid[];
  /** A short label at the tip of a derived arrow: `{ velocity: "v" }`. */
  arrowLabels: Partial<Record<SimulationArrow, string>>;
  /** Faint copies of each body at this many evenly spaced samples. */
  strobe?: number;
  /** One sentence a screen reader says for the picture, instead of the generated one. */
  alt?: string;
  titleKey?: SceneTitleKey;
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
  "pendulum",
];
const MAX_VECTORS = 6;
/** Each of tethers, angles and solids, as the server caps them. */
const MAX_PARTS = 4;
const MAX_SHORT_LABEL = 24;
const MAX_ALT = 300;
const MIN_STROBE = 2;
const MAX_STROBE = 12;

/**
 * A field added in v2 that does not read. Old fields keep their old, lenient
 * reading so a stored reply renders exactly as before; a new field is as
 * strict as the server model, since anything it would refuse is a bug.
 */
class MalformedScene extends Error {}

function reject(): never {
  throw new MalformedScene();
}

/** Length in code points, which is what the server's `max_length` counts. */
function codePoints(text: string): number {
  return Array.from(text).length;
}

/** A strictly finite `[x, y]` pair, or null. */
function readPoint(raw: unknown): { x: number; y: number } | null {
  if (!Array.isArray(raw) || raw.length !== 2) return null;
  const x = finite(raw[0]);
  const y = finite(raw[1]);
  return x === null || y === null ? null : { x, y };
}

/** A new field's `[x, y]`: present and finite, or the scene is refused. */
function requirePoint(raw: unknown): { x: number; y: number } {
  return readPoint(raw) ?? reject();
}

/** An optional label on a new field: absent or null is none, too long is refused. */
function optionalLabel(raw: unknown, max = MAX_SHORT_LABEL): string | undefined {
  if (raw === undefined || raw === null) return undefined;
  if (typeof raw !== "string" || codePoints(raw) > max) reject();
  return raw || undefined;
}

/** A list field: absent is empty, anything but a short enough array is refused. */
function optionalList(raw: unknown, max: number): unknown[] {
  if (raw === undefined) return [];
  if (!Array.isArray(raw) || raw.length > max) reject();
  return raw;
}

function isRecord(raw: unknown): raw is Record<string, unknown> {
  return typeof raw === "object" && raw !== null && !Array.isArray(raw);
}

function isIndex(raw: unknown): raw is number {
  return typeof raw === "number" && Number.isInteger(raw) && raw >= 0;
}

function parseVector(raw: unknown): SimulationVector | null {
  if (!raw || typeof raw !== "object") return null;
  const row = raw as Record<string, unknown>;
  const dx = finite(row.dx);
  const dy = finite(row.dy);
  if (dx === null || dy === null || (dx === 0 && dy === 0)) return null;
  const anchor = readPoint(row.anchor);
  if (!anchor) return null;
  // Range-checked against the bodies once they are all read.
  const body =
    row.body === undefined || row.body === null
      ? undefined
      : isIndex(row.body)
        ? row.body
        : reject();
  return {
    anchor,
    dx,
    dy,
    label: typeof row.label === "string" && row.label ? row.label.slice(0, 24) : undefined,
    // An unknown role is drawn as a plain force: the arrow still says
    // something true about direction, and a newer server never blanks a scene.
    role: VECTOR_ROLES.includes(row.role as SimulationVectorRole)
      ? (row.role as SimulationVectorRole)
      : "force",
    ...(body !== undefined ? { body } : {}),
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
  const shape: SimulationBodyShape =
    row.shape === undefined
      ? "circle"
      : row.shape === "circle" || row.shape === "box"
        ? row.shape
        : reject();
  return {
    label: typeof row.label === "string" && row.label ? row.label.slice(0, 32) : undefined,
    // A non-positive radius would draw nothing at all, so it falls back rather
    // than rendering an invisible body.
    radius: radius !== null && radius > 0 ? radius : 0.4,
    path,
    role: row.role === "secondary" ? "secondary" : "primary",
    shape,
  };
}

function parseTether(raw: unknown): SimulationTether {
  if (!isRecord(raw) || !isIndex(raw.body)) reject();
  return { anchor: requirePoint(raw.anchor), body: raw.body };
}

function parsePulley(raw: unknown): SimulationPulley | undefined {
  if (raw === undefined || raw === null) return undefined;
  if (!isRecord(raw)) reject();
  const radius = finite(raw.radius);
  if (radius === null || radius <= 0) reject();
  return { centre: requirePoint(raw.centre), radius };
}

function parsePlanet(raw: unknown): SimulationPlanet | undefined {
  if (raw === undefined || raw === null) return undefined;
  if (!isRecord(raw)) reject();
  const radius = finite(raw.radius);
  if (radius === null || radius <= 0) reject();
  const label = optionalLabel(raw.label);
  return label ? { radius, label } : { radius };
}

function parseAngle(raw: unknown): SimulationAngle {
  if (!isRecord(raw)) reject();
  const startDeg = finite(raw.start_deg);
  const endDeg = finite(raw.end_deg);
  if (startDeg === null || endDeg === null || startDeg === endDeg) reject();
  const arrow =
    raw.arrow === undefined ? false : typeof raw.arrow === "boolean" ? raw.arrow : reject();
  const role =
    raw.role === undefined
      ? "given"
      : raw.role === "given" || raw.role === "result"
        ? raw.role
        : reject();
  const label = optionalLabel(raw.label);
  return {
    vertex: requirePoint(raw.vertex),
    startDeg,
    endDeg,
    arrow,
    role,
    ...(label ? { label } : {}),
  };
}

function parseSolid(raw: unknown): SimulationSolid {
  if (!isRecord(raw) || !Array.isArray(raw.rect) || raw.rect.length !== 4) reject();
  const [xMin, yMin, xMax, yMax] = raw.rect.map(finite);
  if (xMin === null || yMin === null || xMax === null || yMax === null) reject();
  if (xMax <= xMin || yMax <= yMin) reject();
  const kind =
    raw.kind === undefined
      ? "solid"
      : raw.kind === "solid" || raw.kind === "fluid"
        ? raw.kind
        : reject();
  const label = optionalLabel(raw.label);
  return { rect: { xMin, yMin, xMax, yMax }, kind, ...(label ? { label } : {}) };
}

/** `arrow_labels`: only arrows the scene names, each a short string. */
function parseArrowLabels(
  raw: unknown,
  named: readonly unknown[],
): Partial<Record<SimulationArrow, string>> {
  if (raw === undefined) return {};
  if (!isRecord(raw)) reject();
  const out: Partial<Record<SimulationArrow, string>> = {};
  for (const [key, value] of Object.entries(raw)) {
    if (!ARROW_KINDS.includes(key as SimulationArrow) || !named.includes(key)) reject();
    if (typeof value !== "string" || codePoints(value) > MAX_SHORT_LABEL) reject();
    if (value) out[key as SimulationArrow] = value;
  }
  return out;
}

function parseStrobe(raw: unknown): number | undefined {
  if (raw === undefined || raw === null) return undefined;
  if (!isIndex(raw) || raw < MIN_STROBE || raw > MAX_STROBE) reject();
  return raw;
}

function parseTitleKey(raw: unknown): SceneTitleKey | undefined {
  if (raw === undefined || raw === null) return undefined;
  if (typeof raw !== "string") reject();
  // A key this build does not know only means a newer server named the scene:
  // the English `title` still says what it is, so the scene draws under it.
  return SCENE_TITLE_KEYS.includes(raw as SceneTitleKey) ? (raw as SceneTitleKey) : undefined;
}

/**
 * Read a scene, or return null so the block can show its fallback.
 *
 * Deliberately as strict as the server model: this fence is server-owned, so
 * anything that does not parse is a bug or an invention, and neither should
 * reach the screen as a half-drawn animation. A circuit, a ray diagram and a
 * wave are not body scenes and read as null here; `diagramKind` routes them.
 */
export function parseSimulationSpec(raw: string): SimulationSpec | null {
  let data: unknown;
  try {
    data = JSON.parse(raw.trim());
  } catch {
    return null;
  }
  if (!data || typeof data !== "object") return null;
  try {
    return readScene(data as Record<string, unknown>);
  } catch (error) {
    if (error instanceof MalformedScene) return null;
    throw error;
  }
}

function readScene(row: Record<string, unknown>): SimulationSpec | null {
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

  const namedArrows = Array.isArray(row.arrows) ? row.arrows : [];
  const arrows = namedArrows.filter((a) =>
    ARROW_KINDS.includes(a as SimulationArrow),
  ) as SimulationArrow[];

  const centre = readPoint(row.centre) ?? undefined;
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
  const pivot = beam ? (readPoint(row.pivot) ?? undefined) : undefined;
  const anchor = readPoint(row.anchor) ?? undefined;
  // A spring with no wall would start the coil at the canvas edge, which is
  // not the spring the solver sampled.
  if (row.type === "spring" && (anchor === undefined || bodies.length !== 1)) return null;

  const inclineDeg = finite(row.incline_deg);

  // --- v2 fields: each left out of the fence when unused ---
  const tethers = optionalList(row.tethers, MAX_PARTS).map(parseTether);
  const pulley = parsePulley(row.pulley);
  const centralBody = parsePlanet(row.central_body);
  const angles = optionalList(row.angles, MAX_PARTS).map(parseAngle);
  const solids = optionalList(row.solids, MAX_PARTS).map(parseSolid);
  const arrowLabels = parseArrowLabels(row.arrow_labels, namedArrows);
  const strobe = parseStrobe(row.strobe);
  const alt = optionalLabel(row.alt, MAX_ALT);
  const titleKey = parseTitleKey(row.title_key);

  // A string or an arrow riding on a body the scene does not have would be
  // drawn from nowhere.
  const attached = [
    ...tethers.map((tether) => tether.body),
    ...vectors.flatMap((vector) => (vector.body === undefined ? [] : [vector.body])),
  ];
  if (attached.some((index) => index >= bodies.length)) return null;
  // The planet sits at the centre; with no centre it has nowhere to be.
  if (centralBody && !centre) return null;
  // A pendulum is its bob and its string, or it is a ball floating in space.
  if (row.type === "pendulum" && (bodies.length !== 1 || tethers.length === 0)) return null;

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
  const shownLabels: Partial<Record<SimulationArrow, string>> = {};
  for (const kind of usable) {
    const label = arrowLabels[kind];
    if (label) shownLabels[kind] = label;
  }

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
    tethers,
    pulley,
    centralBody,
    angles,
    solids,
    arrowLabels: shownLabels,
    strobe,
    alt,
    titleKey,
  };
}

/**
 * The scene's title: the translated name when the server sent a key this build
 * knows, else the server's English `title`, else the generic word.
 */
export function sceneTitle(spec: SimulationSpec, t: Translate): string {
  if (spec.titleKey) {
    const key = `rich.scene_title_${spec.titleKey}`;
    const translated = t(key);
    // i18next hands a missing key back unchanged.
    if (translated && translated !== key) return translated;
  }
  return spec.title ?? t("rich.simulation_title");
}

/** Which samples a strobe shows: `count` evenly spaced, first and last included. */
export function strobeIndices(samples: number, count: number | undefined): number[] {
  if (!count || count < 2 || samples < 2) return [];
  const last = samples - 1;
  const out: number[] = [];
  for (let i = 0; i < count; i += 1) {
    const index = Math.round((i * last) / (count - 1));
    if (out[out.length - 1] !== index) out.push(index);
  }
  return out;
}

/**
 * Water in a tank: a domain colour, like an element's in a molecule, picked
 * per scheme. The fill is a translucent wash of it and the surface line is it
 * at full strength.
 */
export const FLUID_TINT = { light: "#2F7ED8", dark: "#64AEF5" } as const;

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

type SimulationTransform = {
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

/** Whether a sampled path comes back to its first sample (to within 1% of its size). */
function endsWhereItStarts(points: readonly ScreenPoint[]): boolean {
  const last = points.length - 1;
  if (last < 3) return false;
  const first = points[0];
  let extent = 0;
  for (const p of points) extent = Math.max(extent, Math.hypot(p.px - first.px, p.py - first.py));
  if (extent === 0) return false;
  return (
    Math.hypot(points[last].px - first.px, points[last].py - first.py) <=
    Math.max(0.5, extent * 0.01)
  );
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
const ARROW_HEAD = 7;
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
function drawsAtWorldScale(spec: SimulationSpec, vector: SimulationVector): boolean {
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
 * Gap between a label and the thing it names. Declared above every worklet
 * that reads it: a worklet captures its constants where it is defined.
 */
const LABEL_GAP = 6;

/**
 * How far from a body's centre its edge is along the unit direction
 * (`ux`, `uy`). A circle is `radius` every way; a box (a square of side
 * 2 * `radius`, turned `boxAngle` radians on screen) is further out toward its
 * corners, so an arrow leaving a block starts on the block, not inside it.
 */
export function bodyEdgeDistance(
  radius: number,
  ux: number,
  uy: number,
  boxAngle: number | null,
): number {
  "worklet";
  if (boxAngle === null) return radius;
  const c = Math.cos(boxAngle);
  const s = Math.sin(boxAngle);
  const along = Math.abs(ux * c + uy * s);
  const across = Math.abs(-ux * s + uy * c);
  const most = along > across ? along : across;
  return most > 1e-9 ? radius / most : radius;
}

/** Half the width of a body's upright bounding box: where its labels clear it. */
export function bodyExtent(radius: number, boxAngle: number | null): number {
  "worklet";
  if (boxAngle === null) return radius;
  return radius * (Math.abs(Math.cos(boxAngle)) + Math.abs(Math.sin(boxAngle)));
}

/** A derived arrow cut short by the ground or a solid is hidden below this, in px. */
export const MIN_CLIPPED_ARROW = 10;

/**
 * The longest an arrow from (`fromX`, `fromY`) along (`ux`, `uy`) can be — at
 * most `length` — before it reaches the ground line (screen y `floorY`) or
 * enters one of `solids` (screen rects). A weight drawn through the floor, or
 * through the table the ball sits on, says the floor is not there.
 */
export function clipArrowLength(
  fromX: number,
  fromY: number,
  ux: number,
  uy: number,
  length: number,
  floorY: number | null,
  solids: readonly { x: number; y: number; width: number; height: number }[],
): number {
  "worklet";
  let limit = length;
  if (floorY !== null && uy > 1e-9) {
    const reach = (floorY - fromY) / uy;
    if (reach < limit) limit = reach > 0 ? reach : 0;
  }
  for (let i = 0; i < solids.length; i += 1) {
    const box = solids[i];
    // Liang–Barsky: the entry parameter of the shaft into the rect, if any.
    let enter = 0;
    let leave = limit;
    let hits = true;
    const edges = [
      [-ux, fromX - box.x],
      [ux, box.x + box.width - fromX],
      [-uy, fromY - box.y],
      [uy, box.y + box.height - fromY],
    ];
    for (let e = 0; e < 4; e += 1) {
      const p = edges[e][0];
      const q = edges[e][1];
      if (Math.abs(p) < 1e-12) {
        if (q < 0) {
          hits = false;
          break;
        }
        continue;
      }
      const r = q / p;
      if (p < 0) {
        if (r > enter) enter = r;
      } else if (r < leave) {
        leave = r;
      }
      if (enter > leave) {
        hits = false;
        break;
      }
    }
    if (hits && enter < limit) limit = enter;
  }
  return limit;
}

/**
 * How far along the unit direction (`ux`, `uy`) a `labelWidth` × `fontSize`
 * box's centre has to be from a point for the box to stay `gap` clear of it.
 * Clearing the point rather than a line across it is what lets a wide label
 * on a slanted arrow sit beside its tip instead of a label-width away.
 */
export function clearanceAlong(
  ux: number,
  uy: number,
  labelWidth: number,
  fontSize: number,
  gap: number,
): number {
  "worklet";
  const a = Math.abs(ux);
  const b = Math.abs(uy);
  const halfW = labelWidth / 2;
  const halfH = fontSize / 2;
  const away = (t: number) => {
    const dx = a * t - halfW;
    const dy = b * t - halfH;
    return Math.hypot(dx > 0 ? dx : 0, dy > 0 ? dy : 0);
  };
  // The support distance always clears it; bisect down to the least that does.
  let high = gap + a * halfW + b * halfH;
  let low = 0;
  for (let i = 0; i < 24; i += 1) {
    const mid = (low + high) / 2;
    if (away(mid) >= gap) high = mid;
    else low = mid;
  }
  return high;
}

/**
 * Top-left of a label box just past an arrow's tip, centred on its line: the
 * same placement `vectorLabelOrigin` gives a stated arrow, as a worklet so a
 * derived arrow's label can follow its tip every frame.
 */
export function tipLabelOrigin(
  tipX: number,
  tipY: number,
  ux: number,
  uy: number,
  labelWidth: number,
  fontSize: number,
): { x: number; y: number } {
  "worklet";
  const reach = clearanceAlong(ux, uy, labelWidth, fontSize, LABEL_GAP);
  return {
    x: tipX + ux * reach - labelWidth / 2,
    y: tipY + uy * reach - fontSize / 2,
  };
}

/**
 * Top-left of a label box beside an arrow's head rather than past it: on the
 * right of the arrow for `side` 1 (below, for a level one), the left for −1.
 * Where something already sits past the tip, the head is the next place a
 * reader looks for the arrow's name.
 */
function besideHeadOrigin(
  tipX: number,
  tipY: number,
  ux: number,
  uy: number,
  length: number,
  labelWidth: number,
  fontSize: number,
  side: number,
): { x: number; y: number } {
  "worklet";
  let nx = -uy;
  let ny = ux;
  if (nx < 0 || (nx === 0 && ny < 0)) {
    nx = -nx;
    ny = -ny;
  }
  if (side < 0) {
    nx = -nx;
    ny = -ny;
  }
  const back = Math.min(ARROW_HEAD, length / 2);
  const reach = LABEL_GAP + (Math.abs(nx) * labelWidth) / 2 + (Math.abs(ny) * fontSize) / 2;
  return {
    x: tipX - ux * back + nx * reach - labelWidth / 2,
    y: tipY - uy * back + ny * reach - fontSize / 2,
  };
}

/**
 * Where an arrow the scene derives (rather than states) is drawn this frame:
 * from the body's edge, along a direction read off the scene, shortened to
 * stay on the canvas. Null when there is nothing to draw — a ball at rest has
 * no velocity, and an arrow toward a centre the body sits on has no direction.
 *
 * Velocity is as long as the body is fast (`velocityArrowLength`); the force
 * arrows have no magnitude to show, so they share one length. With a ground
 * line (`floorY`) or solids in the scene the arrow stops where it would enter
 * them, and one cut to under `MIN_CLIPPED_ARROW` is not drawn at all — the
 * weight of a ball resting on the floor is not an arrow into the floor.
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
    /** Screen rotation of a box body; null or absent for a circle. */
    boxAngle?: number | null;
    /** Screen y of the ground line, when the scene has one. */
    floorY?: number | null;
    /** Screen rects of the scene's solids (not its fluids). */
    solids?: readonly { x: number; y: number; width: number; height: number }[];
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
  const edge = bodyEdgeDistance(radius, ux, uy, context.boxAngle ?? null);
  // Never past the centre it points at.
  if (kind === "centripetal") length = Math.min(length, magnitude - edge - 2);
  if (!(length > 0)) return null;
  const fromX = at.px + ux * edge;
  const fromY = at.py + uy * edge;
  const fit = fitArrowLength(fromX, fromY, ux, uy, length, context.width, context.height);
  if (!(fit > 0)) return null;
  const clipped = clipArrowLength(
    fromX,
    fromY,
    ux,
    uy,
    fit,
    context.floorY ?? null,
    context.solids ?? [],
  );
  if (clipped < fit && clipped < MIN_CLIPPED_ARROW) return null;
  return { fromX, fromY, ux, uy, length: clipped };
}

/**
 * Where a derived arrow's label goes this frame: just past its tip, unless
 * that is in the ground or a solid — the weight of a ball about to land, or
 * resting on a table — and then beside the head, on its right.
 */
export function derivedLabelOrigin(
  arrow: { fromX: number; fromY: number; ux: number; uy: number; length: number },
  labelWidth: number,
  fontSize: number,
  floorY: number | null,
  solids: readonly { x: number; y: number; width: number; height: number }[],
  beside = 0,
): { x: number; y: number } {
  "worklet";
  const tipX = arrow.fromX + arrow.ux * arrow.length;
  const tipY = arrow.fromY + arrow.uy * arrow.length;
  if (beside !== 0) {
    return besideHeadOrigin(
      tipX,
      tipY,
      arrow.ux,
      arrow.uy,
      arrow.length,
      labelWidth,
      fontSize,
      beside,
    );
  }
  const past = tipLabelOrigin(tipX, tipY, arrow.ux, arrow.uy, labelWidth, fontSize);
  let blocked = floorY !== null && tipY <= floorY + 0.5 && past.y + fontSize > floorY;
  for (let i = 0; !blocked && i < solids.length; i += 1) {
    const box = solids[i];
    blocked =
      past.x < box.x + box.width &&
      box.x < past.x + labelWidth &&
      past.y < box.y + box.height &&
      box.y < past.y + fontSize;
  }
  if (!blocked) return past;
  return besideHeadOrigin(tipX, tipY, arrow.ux, arrow.uy, arrow.length, labelWidth, fontSize, 1);
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

/** Skia text is drawn from its baseline, about this far down a line. */
const LABEL_ASCENT = 0.8;

/** The baseline Skia draws a label at, for a label's box. */
function labelBaseline(box: LabelBox): number {
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

export type BodyLabelSide =
  | "above"
  | "below"
  | "right"
  | "left"
  | "below-right"
  | "above-right"
  | "below-left"
  | "above-left";

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
  // Off a corner: clear of anything leaving the body straight up, down or sideways.
  const corner = radius * Math.SQRT1_2 + LABEL_GAP * 0.6;
  switch (side) {
    case "below-right":
      return { dx: corner, dy: corner };
    case "above-right":
      return { dx: corner, dy: -corner - fontSize };
    case "below-left":
      return { dx: -corner - labelWidth, dy: corner };
    case "above-left":
      return { dx: -corner - labelWidth, dy: -corner - fontSize };
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

/** Room kept between a body's label and any line, in px (on top of the 1 px margin). */
const BODY_LABEL_CLEARANCE = 2;

/**
 * The first side, in the body's order of preference, where its label crosses
 * no arrow and fits on the canvas. The primary body prefers above and a
 * secondary body below, so a pair of bodies never shares a label line.
 *
 * For a body that moves, the label rides along at one offset, so a side is
 * only clear if it is clear at every sampled position
 * (`centres[k]`, against `obstacles[k]`) — a pendulum bob's label beside it
 * would sit on its own track as it swings through the bottom. The corners are
 * the last resort; when nothing is clear all the way through, the side clear
 * for the most frames wins.
 */
function chooseBodyLabelSideAcrossFrames(
  centres: readonly ScreenPoint[],
  radius: number,
  labelWidth: number,
  fontSize: number,
  role: SimulationBody["role"],
  obstacles: readonly (readonly Segment[])[],
  width: number,
  height: number,
): BodyLabelSide {
  const order: BodyLabelSide[] =
    role === "secondary"
      ? [
          "below",
          "above",
          "right",
          "left",
          "below-right",
          "below-left",
          "above-right",
          "above-left",
        ]
      : [
          "above",
          "below",
          "right",
          "left",
          "above-right",
          "above-left",
          "below-right",
          "below-left",
        ];
  const conflicts = (side: BodyLabelSide) => {
    const offset = bodyLabelOffset(side, radius, labelWidth, fontSize);
    let count = 0;
    for (let frame = 0; frame < centres.length; frame += 1) {
      const centre = centres[frame];
      let box = {
        x: centre.px + offset.dx - 1,
        y: centre.py + offset.dy - 1,
        width: labelWidth + 2,
        height: fontSize + 2,
      };
      if (frame === 0) {
        const inside =
          box.x >= 0 && box.y >= 0 && box.x + box.width <= width && box.y + box.height <= height;
        if (!inside) return Infinity;
      } else {
        // Later frames keep the label on the canvas, as the renderer does.
        box = clampBox(box, width, height, 0);
      }
      // A little more room than the glyphs: an end tick or an arrowhead
      // reaches past its line.
      const room = inflateBox(box, BODY_LABEL_CLEARANCE);
      if ((obstacles[frame] ?? []).some((segment) => segmentHitsBox(segment, room))) count += 1;
    }
    return count;
  };
  let best: BodyLabelSide = order[0];
  let fewest = Infinity;
  for (const side of order) {
    const count = conflicts(side);
    if (count === 0) return side;
    if (count < fewest) {
      fewest = count;
      best = side;
    }
  }
  return best;
}

/**
 * Top-left of a stated vector's label box. `mid` false puts it just past the
 * arrowhead, centred on the line of the arrow; `mid` true puts it beside the
 * middle of the shaft, on `side` (+1 or −1) of it — which is how a component
 * and a dimension line are labelled, so a component never shares the result's
 * tip. A worklet, so a label riding on a body can follow its arrow.
 */
export function vectorLabelOrigin(
  fromX: number,
  fromY: number,
  tipX: number,
  tipY: number,
  labelWidth: number,
  fontSize: number,
  mid: boolean,
  side: number,
  beside = 0,
): { x: number; y: number } {
  "worklet";
  const dx = tipX - fromX;
  const dy = tipY - fromY;
  const length = Math.hypot(dx, dy) || 1;
  const ux = dx / length;
  const uy = dy / length;
  if (!mid && beside !== 0) {
    return besideHeadOrigin(tipX, tipY, ux, uy, length, labelWidth, fontSize, beside);
  }
  let cx: number;
  let cy: number;
  if (!mid) {
    const r = clearanceAlong(ux, uy, labelWidth, fontSize, LABEL_GAP);
    cx = tipX + ux * r;
    cy = tipY + uy * r;
  } else {
    const nx = -uy * side;
    const ny = ux * side;
    const r = LABEL_GAP + (Math.abs(nx) * labelWidth) / 2 + (Math.abs(ny) * fontSize) / 2;
    cx = (fromX + tipX) / 2 + nx * r;
    cy = (fromY + tipY) / 2 + ny * r;
  }
  return { x: cx - labelWidth / 2, y: cy - fontSize / 2 };
}

/**
 * How far an arrow from (`fromX`, `fromY`) along (`ux`, `uy`) gets — at most
 * `length` — before it meets the circle at (`cx`, `cy`) of `radius`.
 */
export function clipArrowAtCircle(
  fromX: number,
  fromY: number,
  ux: number,
  uy: number,
  length: number,
  cx: number,
  cy: number,
  radius: number,
): number {
  "worklet";
  const ox = cx - fromX;
  const oy = cy - fromY;
  const along = ox * ux + oy * uy;
  if (along <= 0) return length;
  const miss = ox * ox + oy * oy - along * along;
  const reach = radius * radius;
  if (miss > reach) return length;
  const enter = along - Math.sqrt(reach - miss);
  if (enter >= length) return length;
  return enter > 0 ? enter : 0;
}

/**
 * A stated vector riding on a body, this frame: from wherever the body has
 * carried its start, fitted to the canvas, and stopped at a pulley's wheel —
 * the tension along an Atwood rope ends where the rope does. Null when too
 * little of it is left to read.
 */
export function riddenVectorGeometry(
  fromX: number,
  fromY: number,
  ux: number,
  uy: number,
  desired: number,
  width: number,
  height: number,
  wheel: { cx: number; cy: number; radius: number } | null,
): { length: number } | null {
  "worklet";
  let length = fitArrowLength(fromX, fromY, ux, uy, desired, width, height);
  if (wheel) {
    const cut = clipArrowAtCircle(
      fromX,
      fromY,
      ux,
      uy,
      length,
      wheel.cx,
      wheel.cy,
      wheel.radius + 1,
    );
    if (cut < length && cut < MIN_CLIPPED_ARROW) return null;
    length = cut;
  }
  return length > 0 ? { length } : null;
}

/** How a stated vector is drawn. */
type VectorStroke = "force" | "motion" | "measure";

export function vectorStroke(role: SimulationVectorRole): VectorStroke {
  return role === "motion" ? "motion" : role === "measure" ? "measure" : "force";
}

export type PlacedLabel = { text: string; x: number; y: number; box: LabelBox };

export type VectorLayout = {
  vector: SimulationVector;
  from: ScreenPoint;
  tip: ScreenPoint;
  head: number;
  label: PlacedLabel | null;
  /**
   * The body the vector rides on. `from`, `tip` and the label are where it is
   * at the first sample; every frame the renderer starts it where the body
   * has carried `from`, fits it again (`riddenVectorGeometry`) and sets the
   * label from `ride`.
   */
  body: number | null;
  /** For a riding vector: its direction, wanted length and label placement. */
  ride: {
    ux: number;
    uy: number;
    desired: number;
    labelWidth: number;
    mid: boolean;
    side: 1 | -1;
    /** 0 past the tip, or beside the head on its right (1) or left (−1). */
    beside: number;
    /** The nudge that keeps the label clear in every sampled frame. */
    dx: number;
    dy: number;
  } | null;
};

export type BodyLabelLayout = {
  side: BodyLabelSide;
  /** Offset from the body's centre to the label's left edge and baseline. */
  dx: number;
  dy: number;
  width: number;
};

/** An angle's arc, its head when it is a moment arrow, and its label. */
export type AngleLayout = {
  angle: SimulationAngle;
  vertex: ScreenPoint;
  radius: number;
  /** The arc as a polyline; a moment arrow's stops short of its head. */
  arc: ScreenPoint[];
  head: { tip: ScreenPoint; ux: number; uy: number; size: number } | null;
  label: PlacedLabel | null;
};

/**
 * A label on a derived arrow. The arrow is worked out every frame, so the
 * label is too: at its tip (`tipLabelOrigin`), moved by (`dx`, `dy`) — the
 * one nudge that keeps it clear in every frame the layout sampled.
 */
export type ArrowLabelLayout = {
  body: number;
  kind: SimulationArrow;
  text: string;
  width: number;
  /** 0 past the tip, or beside the head on its right (1) or left (−1). */
  beside: number;
  dx: number;
  dy: number;
};

export type SolidLayout = { solid: SimulationSolid; box: LabelBox; label: PlacedLabel | null };

export type PlanetLayout = { centre: ScreenPoint; radius: number; label: PlacedLabel | null };

/** A short hatched bar: the fixed point a string hangs from. */
export type SupportLayout = { bar: Segment; hatches: Segment[] };

export type TetherLayout = {
  anchor: ScreenPoint;
  body: number;
  /** Null when the string leaves a pulley's rim, which is its support. */
  support: SupportLayout | null;
};

export type PulleyLayout = {
  centre: ScreenPoint;
  radius: number;
  /** The rope over the top of the wheel, between the strings that leave its rim. */
  rope: ScreenPoint[] | null;
};

export type SceneLayout = {
  radii: number[];
  /** Screen rotation of each box body, in radians; null for a circle. */
  boxAngles: (number | null)[];
  /** Each body's path on screen. */
  tracks: ScreenPoint[][];
  closed: boolean[];
  /** The fastest any body moves, for velocity arrow lengths; 0 without them. */
  maxSpeed: number;
  /** Screen y of the ground line, when the scene has one. */
  floorY: number | null;
  /** Screen rects a derived arrow stops at (solids, not fluids). */
  obstacles: LabelBox[];
  vectors: VectorLayout[];
  bodyLabels: (BodyLabelLayout | null)[];
  angles: AngleLayout[];
  arrowLabels: ArrowLabelLayout[];
  solids: SolidLayout[];
  planet: PlanetLayout | null;
  tethers: TetherLayout[];
  pulley: PulleyLayout | null;
  /** A pendulum's dashed rest line under each pivot. */
  restLines: Segment[];
  /** Where each body's faint strobe copies sit; empty for a body that never moves. */
  strobes: ScreenPoint[][];
};

/** The smallest a body is drawn, so a 2 cm ball is still a dot. */
const MIN_BODY_RADIUS = 4;

function unit(dx: number, dy: number): { ux: number; uy: number } {
  const length = Math.hypot(dx, dy) || 1;
  return { ux: dx / length, uy: dy / length };
}

function isStationary(body: SimulationBody): boolean {
  const [x0, y0] = body.path[0];
  return body.path.every(([x, y]) => x === x0 && y === y0);
}

/**
 * How a body's box is turned on screen: onto the slope in an incline scene,
 * upright anywhere else. Null for a circle.
 */
export function bodyBoxAngle(spec: SimulationSpec, body: SimulationBody): number | null {
  if (body.shape !== "box") return null;
  if (spec.type === "incline" && spec.inclineDeg !== undefined) {
    // Descending left to right is clockwise on a y-down screen.
    return (spec.inclineDeg * Math.PI) / 180;
  }
  return 0;
}

/**
 * Where a string ends: at the edge of its body, on the line from its anchor
 * to the body's centre. Null when the anchor is inside the body.
 */
export function tetherEnd(
  anchor: ScreenPoint,
  centre: ScreenPoint,
  radius: number,
  boxAngle: number | null,
): ScreenPoint | null {
  "worklet";
  const dx = centre.px - anchor.px;
  const dy = centre.py - anchor.py;
  const length = Math.hypot(dx, dy);
  if (!(length > 0)) return null;
  const ux = dx / length;
  const uy = dy / length;
  const edge = bodyEdgeDistance(radius, ux, uy, boxAngle);
  if (length <= edge) return null;
  return { px: centre.px - ux * edge, py: centre.py - uy * edge };
}

/** Half the length of a string's support bar, and how far its hatching reaches. */
const SUPPORT_HALF = 12;
const SUPPORT_HATCH = 5;
const SUPPORT_HATCHES = 5;

/**
 * A ceiling (or a wall) for a string to hang from: a bar across the string's
 * line at the anchor, hatched on the side away from the body.
 */
export function supportGeometry(anchor: ScreenPoint, toward: ScreenPoint): SupportLayout {
  const dx = toward.px - anchor.px;
  const dy = toward.py - anchor.py;
  // Snapped to the nearer axis: a pendulum hangs from a level ceiling even
  // when its first sample is the bob at full swing.
  const vertical = Math.abs(dy) >= Math.abs(dx);
  const away = vertical ? (dy >= 0 ? -1 : 1) : dx >= 0 ? -1 : 1;
  const bar: Segment = vertical
    ? { x1: anchor.px - SUPPORT_HALF, y1: anchor.py, x2: anchor.px + SUPPORT_HALF, y2: anchor.py }
    : { x1: anchor.px, y1: anchor.py - SUPPORT_HALF, x2: anchor.px, y2: anchor.py + SUPPORT_HALF };
  const hatches: Segment[] = [];
  for (let i = 0; i < SUPPORT_HATCHES; i += 1) {
    const along = -SUPPORT_HALF + ((i + 0.5) * (SUPPORT_HALF * 2)) / SUPPORT_HATCHES;
    const x = vertical ? anchor.px + along : anchor.px;
    const y = vertical ? anchor.py : anchor.py + along;
    hatches.push(
      vertical
        ? { x1: x, y1: y, x2: x - SUPPORT_HATCH, y2: y + away * SUPPORT_HATCH }
        : { x1: x, y1: y, x2: x + away * SUPPORT_HATCH, y2: y - SUPPORT_HATCH },
    );
  }
  return { bar, hatches };
}

/** Whether a point sits on a pulley's rim (within a pixel and a half). */
export function onPulleyRim(point: ScreenPoint, centre: ScreenPoint, radius: number): boolean {
  return (
    Math.abs(Math.hypot(point.px - centre.px, point.py - centre.py) - radius) <=
    Math.max(1.5, radius * 0.03)
  );
}

/**
 * The rope over the top of a pulley: the arc of the rim between the leftmost
 * and rightmost strings that leave it, the way that passes over the top.
 */
export function pulleyRope(
  centre: ScreenPoint,
  radius: number,
  rim: readonly ScreenPoint[],
): ScreenPoint[] | null {
  if (rim.length < 2) return null;
  const sorted = [...rim].sort((a, b) => a.px - b.px);
  const TAU = Math.PI * 2;
  const angle = (p: ScreenPoint) => {
    const a = Math.atan2(p.py - centre.py, p.px - centre.px);
    return a < 0 ? a + TAU : a;
  };
  let from = angle(sorted[0]);
  let to = angle(sorted[sorted.length - 1]);
  // Screen angles grow clockwise; the top of the wheel is 3π/2.
  if (to <= from) to += TAU;
  const top = Math.PI * 1.5;
  const passesTop = (top >= from && top <= to) || (top + TAU >= from && top + TAU <= to);
  if (!passesTop) [from, to] = [to, from + TAU];
  const steps = Math.max(4, Math.ceil((to - from) / ((6 * Math.PI) / 180)));
  return Array.from({ length: steps + 1 }, (_, i) => {
    const a = from + ((to - from) * i) / steps;
    return { px: centre.px + radius * Math.cos(a), py: centre.py + radius * Math.sin(a) };
  });
}

/** Screen radius of an angle's arc. */
export const ANGLE_RADIUS = 26;
/** A narrow angle's arc is drawn further out, so it is a visible curve rather than a tick... */
const ANGLE_MIN_ARC = 14;
/** ...but never so far out that it stops reading as the angle at its vertex. */
export const ANGLE_MAX_RADIUS = 56;
const ANGLE_STEP_DEG = 4;

/** The signed sweep from `startDeg` to `endDeg`, never more than a full turn. */
function angleSweep(startDeg: number, endDeg: number): number {
  const sweep = endDeg - startDeg;
  return Math.max(-360, Math.min(360, sweep));
}

export function angleRadius(startDeg: number, endDeg: number): number {
  const sweep = (Math.abs(angleSweep(startDeg, endDeg)) * Math.PI) / 180;
  return Math.max(ANGLE_RADIUS, Math.min(ANGLE_MAX_RADIUS, ANGLE_MIN_ARC / sweep));
}

/** A point on an arc, `deg` counter-clockwise from +x in the world (y up). */
function arcPoint(vertex: ScreenPoint, radius: number, deg: number): ScreenPoint {
  const rad = (deg * Math.PI) / 180;
  return { px: vertex.px + radius * Math.cos(rad), py: vertex.py - radius * Math.sin(rad) };
}

/** An arc from `startDeg` to `endDeg` as a polyline, in steps of a few degrees. */
export function angleArcPoints(
  vertex: ScreenPoint,
  startDeg: number,
  endDeg: number,
  radius: number,
): ScreenPoint[] {
  const sweep = angleSweep(startDeg, endDeg);
  const steps = Math.max(2, Math.ceil(Math.abs(sweep) / ANGLE_STEP_DEG));
  return Array.from({ length: steps + 1 }, (_, i) =>
    arcPoint(vertex, radius, startDeg + (sweep * i) / steps),
  );
}

/** The tip of a moment arrow at `endDeg`, pointing the way the arc turns. */
export function angleArrowHead(
  vertex: ScreenPoint,
  startDeg: number,
  endDeg: number,
  radius: number,
): { tip: ScreenPoint; ux: number; uy: number } {
  const sweep = angleSweep(startDeg, endDeg);
  const end = startDeg + sweep;
  const rad = (end * Math.PI) / 180;
  const turn = sweep > 0 ? 1 : -1;
  // d/dθ of (cos θ, −sin θ), the arc on a y-down screen.
  return {
    tip: arcPoint(vertex, radius, end),
    ux: -Math.sin(rad) * turn,
    uy: -Math.cos(rad) * turn,
  };
}

/** An angle's label box: outside the arc, centred on its middle angle. */
export function angleLabelBox(
  vertex: ScreenPoint,
  startDeg: number,
  endDeg: number,
  radius: number,
  labelWidth: number,
  fontSize: number,
): LabelBox {
  const mid = ((startDeg + angleSweep(startDeg, endDeg) / 2) * Math.PI) / 180;
  const ux = Math.cos(mid);
  const uy = -Math.sin(mid);
  const reach = LABEL_GAP + (Math.abs(ux) * labelWidth) / 2 + (Math.abs(uy) * fontSize) / 2;
  const cx = vertex.px + ux * (radius + reach);
  const cy = vertex.py + uy * (radius + reach);
  return { x: cx - labelWidth / 2, y: cy - fontSize / 2, width: labelWidth, height: fontSize };
}

/**
 * Where a label goes once nudged: its home box kept on the canvas, moved by
 * (`dx`, `dy`), and kept on the canvas again — the same steps the layout
 * takes, so a label the renderer places every frame lands where the layout
 * checked it. Returns the left edge and the baseline.
 */
export function placeNudgedLabel(
  x: number,
  y: number,
  labelWidth: number,
  fontSize: number,
  dx: number,
  dy: number,
  width: number,
  height: number,
): { x: number; y: number; baseline: number } {
  "worklet";
  const inset = 4;
  const maxX = width - inset - labelWidth;
  const maxY = height - inset - fontSize;
  let left = x < inset ? inset : x > maxX ? maxX : x;
  let top = y < inset ? inset : y > maxY ? maxY : y;
  left += dx;
  top += dy;
  left = left < inset ? inset : left > maxX ? maxX : left;
  top = top < inset ? inset : top > maxY ? maxY : top;
  // Matches LABEL_ASCENT; a worklet cannot reach a module constant declared below it.
  return { x: left, y: top, baseline: top + fontSize * 0.8 };
}

/** Progress values the label pass checks a moving scene at. */
const LAYOUT_FRAMES = 17;

type FrameLabel = {
  /**
   * The home box at each sampled frame, null where the label is not drawn —
   * for each place the label may go, in order of preference: past an arrow's
   * tip first, then beside its head on either side.
   */
  homes: (LabelBox | null)[][];
  /**
   * Each frame's box is placed on its own (a derived arrow's label, worked out
   * every frame), or the first frame's box is placed and the rest ride along
   * by the same offset (a label on a body-borne vector, moved as a whole).
   */
  each: boolean;
  avoid: Segment[][];
};

function shiftBox(box: LabelBox, dx: number, dy: number): LabelBox {
  return { ...box, x: box.x + dx, y: box.y + dy };
}

/** What a clash in the first frame costs: that frame is the still picture Reduce Motion shows. */
const FIRST_FRAME_CLASH = 1000;
/** Pixels of nudge worth one later frame of overlap. */
const NUDGE_PER_FRAME = 8;
/** What leaving the tip for the side of the head costs, in the same points (12 px of nudge). */
const ALTERNATE_HOME = 1.5;

/**
 * `separateLabels` across time. Each label, in priority order, tries the same
 * nudges in the same order and keeps the cheapest: a clash with anything
 * placed before it, or with a line it must avoid, costs a lot in the first
 * frame (the still picture) and one point in any later frame, and every
 * `NUDGE_PER_FRAME` px of nudge costs a point. A label riding on a body thus
 * stays at its arrow's tip and only gives way where it would be covered for
 * much of the motion. With one frame this is exactly `separateLabels`.
 */
function separateAcrossFrames(
  labels: readonly FrameLabel[],
  fixed: readonly LabelBox[][],
  width: number,
  height: number,
  gap = 2,
): { home: number; dx: number; dy: number; boxes: (LabelBox | null)[] }[] {
  const frames = fixed.length;
  const placed: LabelBox[][] = fixed.map((boxes) => [...boxes]);
  return labels.map((label) => {
    const candidate = (home: (LabelBox | null)[], dx: number, dy: number): (LabelBox | null)[] => {
      const first = home.find((box) => box !== null) ?? null;
      return home.map((box) => {
        if (!box) return null;
        if (label.each || !first)
          return clampBox(shiftBox(clampBox(box, width, height), dx, dy), width, height);
        const moved = clampBox(shiftBox(clampBox(first, width, height), dx, dy), width, height);
        return shiftBox(moved, box.x - first.x, box.y - first.y);
      });
    };
    const clashes = (boxes: (LabelBox | null)[]) => {
      let cost = 0;
      boxes.forEach((box, frame) => {
        if (!box || frame >= frames) return;
        const lines = label.avoid[frame] ?? [];
        const clash =
          placed[frame].some((other) => boxesOverlap(box, other, gap)) ||
          lines.some((line) => segmentHitsBox(line, inflateBox(box, LINE_CLEARANCE)));
        if (clash) cost += frame === 0 ? FIRST_FRAME_CLASH : 1;
      });
      return cost;
    };
    let choice = { home: 0, dx: 0, dy: 0 };
    let boxes = candidate(label.homes[0] ?? [], 0, 0);
    let best = clashes(boxes);
    label.homes.forEach((home, index) => {
      const penalty = index === 0 ? 0 : ALTERNATE_HOME;
      if (penalty >= best) return;
      const atHome = candidate(home, 0, 0);
      const cost = clashes(atHome) + penalty;
      if (cost < best) {
        best = cost;
        choice = { home: index, dx: 0, dy: 0 };
        boxes = atHome;
      }
      for (let step = NUDGE_STEP; step <= MAX_NUDGE; step += NUDGE_STEP) {
        // Nothing further out can beat what is already in hand.
        if (penalty + step / NUDGE_PER_FRAME >= best) break;
        for (const [dx, dy] of [
          [0, step],
          [0, -step],
          [step, 0],
          [-step, 0],
        ]) {
          const moved = candidate(home, dx, dy);
          const total = clashes(moved) + penalty + step / NUDGE_PER_FRAME;
          if (total < best) {
            best = total;
            choice = { home: index, dx, dy };
            boxes = moved;
          }
        }
      }
    });
    boxes.forEach((box, frame) => {
      if (box && frame < frames) placed[frame].push(box);
    });
    return { ...choice, boxes };
  });
}

function segmentOf(from: ScreenPoint, tip: ScreenPoint): Segment {
  return { x1: from.px, y1: from.py, x2: tip.px, y2: tip.py };
}

function polylineSegments(points: readonly ScreenPoint[]): Segment[] {
  return points.slice(1).map((point, i) => segmentOf(points[i], point));
}

function placedLabel(text: string, box: LabelBox): PlacedLabel {
  return { text, x: box.x, y: labelBaseline(box), box };
}

/**
 * Every static piece of a scene's layout, worked out once per size: stated
 * vectors with their lengths, canvas fit and labels, which side of each body
 * its label goes, the angles, solids, strings and pulley, and where each
 * derived arrow's label sits relative to its tip.
 *
 * `measureText` is the font's width for a string. A scene that moves is
 * checked at `LAYOUT_FRAMES` moments, not just its first: a label riding on a
 * body is nudged once, so it has to be clear all the way through.
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
  const boxAngles = spec.bodies.map((body) => bodyBoxAngle(spec, body));
  const extents = radii.map((radius, index) => bodyExtent(radius, boxAngles[index]));
  const tracks = spec.bodies.map((body) => projectPath(body.path, transform));
  // A pendulum is sampled over whole swings, and turns round at the join, so
  // `isClosedPath` (which wants motion carrying straight on) never says so;
  // wrapping its window there is what gives the bob no velocity at full swing.
  const closed = tracks.map(
    (track) => isClosedPath(track) || (spec.type === "pendulum" && endsWhereItStarts(track)),
  );
  const maxSpeed = spec.arrows.includes("velocity")
    ? tracks.reduce((best, track, index) => Math.max(best, maxTrackSpeed(track, closed[index])), 0)
    : 0;
  const floorY = spec.ground ? worldToScreen(0, 0, transform).py : null;
  const solidBoxes = spec.solids.map((solid) => {
    const topLeft = worldToScreen(solid.rect.xMin, solid.rect.yMax, transform);
    const bottomRight = worldToScreen(solid.rect.xMax, solid.rect.yMin, transform);
    return {
      x: topLeft.px,
      y: topLeft.py,
      width: bottomRight.px - topLeft.px,
      height: bottomRight.py - topLeft.py,
    };
  });
  const obstacles = solidBoxes.filter((_, index) => spec.solids[index].kind === "solid");
  const pivot = spec.pivot && spec.beam ? worldToScreen(spec.pivot.x, spec.pivot.y, transform) : null;
  const lengths = vectorScreenLengths(spec, transform.scale);
  const centre = spec.centre ? worldToScreen(spec.centre.x, spec.centre.y, transform) : null;
  const slope = spec.inclineDeg !== undefined ? inclineDirections(spec.inclineDeg) : null;

  const animated = simulationIsAnimated(spec);
  const progresses = animated
    ? Array.from({ length: LAYOUT_FRAMES }, (_, i) => i / (LAYOUT_FRAMES - 1))
    : [0];
  /** Each body's centre at each sampled frame. */
  const positions = tracks.map((track) =>
    progresses.map((progress) => samplePathAt(track, progress * (track.length - 1))),
  );
  /** How far each body has moved by each sampled frame. */
  const shifts = positions.map((frames) =>
    frames.map((point) => ({ dx: point.px - frames[0].px, dy: point.py - frames[0].py })),
  );

  const pulleyCentre = spec.pulley
    ? worldToScreen(spec.pulley.centre.x, spec.pulley.centre.y, transform)
    : null;
  const pulleyRadius = spec.pulley ? spec.pulley.radius * transform.scale : 0;
  const wheel = pulleyCentre
    ? { cx: pulleyCentre.px, cy: pulleyCentre.py, radius: pulleyRadius }
    : null;

  // --- stated vectors ---------------------------------------------------------
  const shafts = spec.vectors.map((vector, index) => {
    // World y is up and screen y is down.
    const { ux, uy } = unit(vector.dx, -vector.dy);
    const body = vector.body ?? null;
    let from: ScreenPoint;
    let onBody: number | null = null;
    if (body !== null) {
      // Riding on a body: the anchor is an offset from where it is.
      const [bx, by] = spec.bodies[body].path[0];
      from = worldToScreen(bx + vector.anchor.x, by + vector.anchor.y, transform);
      if (Math.hypot(vector.anchor.x, vector.anchor.y) * transform.scale < 0.5) onBody = body;
    } else {
      from = worldToScreen(vector.anchor.x, vector.anchor.y, transform);
      if (pivot) from = leverLoadAnchor(from, uy, pivot);
      // A body is drawn over the arrows that start at its centre, so an arrow
      // anchored on a still body starts at its edge instead: the part you see
      // is then the whole length, and two forces keep their proportions.
      const still = spec.bodies.findIndex(
        (candidate, i) =>
          isStationary(candidate) &&
          Math.hypot(positions[i][0].px - from.px, positions[i][0].py - from.py) < 0.5,
      );
      if (still >= 0) onBody = still;
    }
    if (onBody !== null) {
      const edge = bodyEdgeDistance(radii[onBody], ux, uy, boxAngles[onBody]);
      from = { px: from.px + ux * edge, py: from.py + uy * edge };
    }
    const desired = lengths[index];
    const still = fitArrowLength(from.px, from.py, ux, uy, desired, width, height);
    /** Where the shaft runs at each frame; null where too little of it is left to draw. */
    const frames = progresses.map((_, frame) => {
      if (body === null) {
        return { from, tip: { px: from.px + ux * still, py: from.py + uy * still } };
      }
      const { dx, dy } = shifts[body][frame];
      const start = { px: from.px + dx, py: from.py + dy };
      const ride = riddenVectorGeometry(start.px, start.py, ux, uy, desired, width, height, wheel);
      return ride
        ? { from: start, tip: { px: start.px + ux * ride.length, py: start.py + uy * ride.length } }
        : null;
    });
    const first = frames[0];
    const tip = first ? first.tip : from;
    const length = Math.hypot(tip.px - from.px, tip.py - from.py);
    return { vector, from, tip, head: arrowHeadSize(length), body, ux, uy, desired, frames };
  });
  /** Each stated vector's shaft at each frame. */
  const vectorLines = shafts.map(({ frames }) =>
    frames.map((shaft) => (shaft ? segmentOf(shaft.from, shaft.tip) : null)),
  );

  // --- derived arrows, at every sampled frame ------------------------------
  const derived = spec.bodies.flatMap((_, body) =>
    spec.arrows.map((kind) => ({
      body,
      kind,
      frames: progresses.map((progress, frame) =>
        derivedArrowGeometry(kind, positions[body][frame], radii[body], {
          tangent:
            kind === "velocity"
              ? tangentAt(tracks[body], progress, closed[body])
              : { dx: 0, dy: 0 },
          maxSpeed,
          centre,
          slope,
          width,
          height,
          boxAngle: boxAngles[body],
          floorY,
          solids: obstacles,
        }),
      ),
    })),
  );
  const derivedLines = derived.map(({ frames }) =>
    frames.map((arrow) =>
      arrow
        ? {
            x1: arrow.fromX,
            y1: arrow.fromY,
            x2: arrow.fromX + arrow.ux * arrow.length,
            y2: arrow.fromY + arrow.uy * arrow.length,
          }
        : null,
    ),
  );

  // --- strings and the pulley ----------------------------------------------
  const tethers: TetherLayout[] = spec.tethers.map((tether) => {
    const anchor = worldToScreen(tether.anchor.x, tether.anchor.y, transform);
    const rim = pulleyCentre !== null && onPulleyRim(anchor, pulleyCentre, pulleyRadius);
    return {
      anchor,
      body: tether.body,
      support: rim ? null : supportGeometry(anchor, positions[tether.body][0]),
    };
  });
  // A pendulum's rest line: straight down from the pivot, as long as the
  // string. The angle it swings through is measured from it.
  const restLines: Segment[] =
    spec.type === "pendulum"
      ? tethers.map(({ anchor, body }) => {
          const bob = positions[body][0];
          const length = Math.hypot(bob.px - anchor.px, bob.py - anchor.py);
          return { x1: anchor.px, y1: anchor.py, x2: anchor.px, y2: anchor.py + length };
        })
      : [];
  const tetherLines = tethers.map(({ anchor, body }) =>
    progresses.map((_, frame) => {
      const end = tetherEnd(anchor, positions[body][frame], radii[body], boxAngles[body]);
      return end ? segmentOf(anchor, end) : null;
    }),
  );
  const pulley: PulleyLayout | null = pulleyCentre
    ? {
        centre: pulleyCentre,
        radius: pulleyRadius,
        rope: pulleyRope(
          pulleyCentre,
          pulleyRadius,
          tethers.filter((tether) => tether.support === null).map((tether) => tether.anchor),
        ),
      }
    : null;

  // --- angles ------------------------------------------------------------------
  const angleShapes = spec.angles.map((angle) => {
    const vertex = worldToScreen(angle.vertex.x, angle.vertex.y, transform);
    const radius = angleRadius(angle.startDeg, angle.endDeg);
    let arc = angleArcPoints(vertex, angle.startDeg, angle.endDeg, radius);
    let head: AngleLayout["head"] = null;
    if (angle.arrow) {
      const end = angleArrowHead(vertex, angle.startDeg, angle.endDeg, radius);
      head = { ...end, size: ARROW_HEAD };
      // Stop the stroke under the head, so its round cap does not poke through.
      const sweep = angleSweep(angle.startDeg, angle.endDeg);
      const short = ((ARROW_HEAD * 0.6) / radius) * (180 / Math.PI) * (sweep > 0 ? 1 : -1);
      if (Math.abs(short) < Math.abs(sweep)) {
        arc = angleArcPoints(vertex, angle.startDeg, angle.startDeg + sweep - short, radius);
      }
    }
    return { angle, vertex, radius, arc, head };
  });
  const arcLines = angleShapes.map(({ arc, head }) => [
    ...polylineSegments(arc),
    ...(head ? [segmentOf(arc[arc.length - 1], head.tip)] : []),
  ]);

  /** Every line a label must stay off at `frame`, leaving out its own. */
  const linesAt = (frame: number, skip: { vector?: number; derived?: number; angle?: number }) => {
    const lines: Segment[] = [];
    vectorLines.forEach((frames, i) => {
      const line = frames[frame];
      if (i !== skip.vector && line) lines.push(line);
    });
    derivedLines.forEach((frames, i) => {
      const line = frames[frame];
      if (i !== skip.derived && line) lines.push(line);
    });
    for (const frames of tetherLines) {
      const line = frames[frame];
      if (line) lines.push(line);
    }
    lines.push(...restLines);
    arcLines.forEach((segments, i) => {
      if (i !== skip.angle) lines.push(...segments);
    });
    return lines;
  };

  // --- what labels keep clear of -------------------------------------------
  const fixed: LabelBox[][] = progresses.map(() => []);
  spec.bodies.forEach((body, index) => {
    const extent = extents[index];
    positions[index].forEach((point, frame) => {
      fixed[frame].push({
        x: point.px - extent,
        y: point.py - extent,
        width: extent * 2,
        height: extent * 2,
      });
    });
  });
  if (pulley) {
    for (const boxes of fixed) {
      boxes.push({
        x: pulley.centre.px - pulley.radius,
        y: pulley.centre.py - pulley.radius,
        width: pulley.radius * 2,
        height: pulley.radius * 2,
      });
    }
  }

  // Solids are labelled inside, near their top-left corner.
  const solids: SolidLayout[] = spec.solids.map((solid, index) => {
    const box = solidBoxes[index];
    if (!solid.label) return { solid, box, label: null };
    const labelBox = clampBox(
      { x: box.x + 4, y: box.y + 4, width: measureText(solid.label), height: fontSize },
      width,
      height,
    );
    for (const boxes of fixed) boxes.push(labelBox);
    return { solid, box, label: placedLabel(solid.label, labelBox) };
  });

  // The planet's name goes in the middle of it, or under it if it does not fit.
  let planet: PlanetLayout | null = null;
  if (spec.centralBody && centre) {
    const radius = spec.centralBody.radius * transform.scale;
    let label: PlacedLabel | null = null;
    if (spec.centralBody.label) {
      const labelWidth = measureText(spec.centralBody.label);
      // A labelled centripetal arrow ends near the centre, label and all, so
      // the planet's name moves down to where its chord still holds it.
      const drop = spec.arrowLabels.centripetal ? 0.55 : 0;
      const chord = 2 * radius * Math.sqrt(1 - drop * drop);
      const fits = labelWidth + 8 <= chord * 0.9 && fontSize + 4 <= radius * 2 * (1 - drop);
      const box = clampBox(
        {
          x: centre.px - labelWidth / 2,
          y: fits ? centre.py + radius * drop - fontSize / 2 : centre.py + radius + LABEL_GAP,
          width: labelWidth,
          height: fontSize,
        },
        width,
        height,
      );
      for (const boxes of fixed) boxes.push(box);
      label = placedLabel(spec.centralBody.label, box);
    }
    planet = { centre, radius, label };
  }

  // --- body labels ---------------------------------------------------------------
  const groundLine: Segment[] =
    floorY === null ? [] : [{ x1: 0, y1: floorY, x2: width, y2: floorY }];
  const bodyLabels = spec.bodies.map((body, index) => {
    if (!body.label) return null;
    const extent = extents[index];
    const labelWidth = measureText(body.label);
    // Its own path counts too: a label riding beside a body that moves
    // sideways would sit on the track it is about to run along.
    const track = isStationary(body) ? [] : polylineSegments(tracks[index]);
    const obstaclesAt = progresses.map((_, frame) => [
      ...vectorLines.flatMap((frames) => (frames[frame] ? [frames[frame]!] : [])),
      ...derived.flatMap((entry, i) => {
        const line = derivedLines[i][frame];
        return entry.body === index && line ? [line] : [];
      }),
      ...tetherLines.flatMap((frames) => (frames[frame] ? [frames[frame]!] : [])),
      ...restLines,
      ...groundLine,
      ...track,
    ]);
    const side = chooseBodyLabelSideAcrossFrames(
      positions[index],
      extent,
      labelWidth,
      fontSize,
      body.role,
      obstaclesAt,
      width,
      height,
    );
    const offset = bodyLabelOffset(side, extent, labelWidth, fontSize);
    positions[index].forEach((point, frame) => {
      // The renderer keeps a moving label on the canvas every frame.
      fixed[frame].push(
        clampBox(
          { x: point.px + offset.dx, y: point.py + offset.dy, width: labelWidth, height: fontSize },
          width,
          height,
        ),
      );
    });
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
  for (const frames of positions) {
    sumX += frames[0].px;
    sumY += frames[0].py;
    count += 1;
  }
  const centroid = count > 0 ? { px: sumX / count, py: sumY / count } : { px: width / 2, py: height / 2 };

  // --- the labels that get nudged, most important first -------------------
  type Wanted = {
    kind: "vector" | "angle" | "derived";
    index: number;
    result: boolean;
    label: FrameLabel;
  };
  const wanted: Wanted[] = [];
  /** How each labelled vector's label is placed: beside its middle, or past its tip. */
  const vectorLabelPlans = shafts.map(({ vector, from, ux, uy, desired, frames }) => {
    if (!vector.label) return null;
    const labelWidth = measureText(vector.label);
    const mid =
      vector.role === "measure" || (spec.type === "vector_sum" && vector.role !== "result");
    const tip = frames[0]?.tip ?? { px: from.px + ux * desired, py: from.py + uy * desired };
    let side: 1 | -1 = 1;
    if (mid) {
      const midX = (from.px + tip.px) / 2 - centroid.px;
      const midY = (from.py + tip.py) / 2 - centroid.py;
      side = -uy * midX + ux * midY >= 0 ? 1 : -1;
    }
    return { labelWidth, mid, side };
  });
  shafts.forEach(({ vector, body, frames }, index) => {
    const plan = vectorLabelPlans[index];
    if (!plan) return;
    const boxAt = (shaft: (typeof frames)[number], beside: number): LabelBox | null => {
      if (!shaft) return null;
      const origin = vectorLabelOrigin(
        shaft.from.px,
        shaft.from.py,
        shaft.tip.px,
        shaft.tip.py,
        plan.labelWidth,
        fontSize,
        plan.mid,
        plan.side,
        beside,
      );
      return { x: origin.x, y: origin.y, width: plan.labelWidth, height: fontSize };
    };
    // A label beside a middle has one place; one past a tip may also sit beside the head.
    const besides = plan.mid ? [0] : [0, 1, -1];
    wanted.push({
      kind: "vector",
      index,
      result: vector.role === "result",
      label: {
        homes: besides.map((beside) => frames.map((shaft) => boxAt(shaft, beside))),
        // A riding vector is refitted every frame, so its label is placed every frame.
        each: body !== null,
        // Its own line too: a label is past its arrow's tip or beside its
        // middle, and a nudge back onto the arrow would strike it through.
        avoid: progresses.map((_, frame) => linesAt(frame, {})),
      },
    });
  });
  angleShapes.forEach(({ angle, vertex, radius }, index) => {
    if (!angle.label) return;
    const box = angleLabelBox(
      vertex,
      angle.startDeg,
      angle.endDeg,
      radius,
      measureText(angle.label),
      fontSize,
    );
    wanted.push({
      kind: "angle",
      index,
      result: angle.role === "result",
      label: {
        homes: [progresses.map(() => box)],
        each: false,
        avoid: progresses.map((_, frame) => linesAt(frame, { angle: index })),
      },
    });
  });
  derived.forEach(({ kind, frames }, index) => {
    const text = spec.arrowLabels[kind];
    if (!text) return;
    const labelWidth = measureText(text);
    wanted.push({
      kind: "derived",
      index,
      result: false,
      label: {
        homes: [0, 1, -1].map((beside) =>
          frames.map((arrow) => {
            if (!arrow) return null;
            const origin = derivedLabelOrigin(
              arrow,
              labelWidth,
              fontSize,
              floorY,
              obstacles,
              beside,
            );
            return { x: origin.x, y: origin.y, width: labelWidth, height: fontSize };
          }),
        ),
        each: true,
        // Its own arrow too: pushed back onto the canvas, a label past the tip
        // would sit on the arrowhead it names.
        avoid: progresses.map((_, frame) => linesAt(frame, {})),
      },
    });
  });
  // The answer keeps its place; everything else moves out of its way.
  const order = wanted
    .map((entry, position) => ({ entry, position }))
    .sort((a, b) => Number(b.entry.result) - Number(a.entry.result) || a.position - b.position)
    .map(({ entry }) => entry);
  const separated = separateAcrossFrames(
    order.map((entry) => entry.label),
    fixed,
    width,
    height,
  );
  const outcome = new Map(order.map((entry, i) => [`${entry.kind}:${entry.index}`, separated[i]]));

  const vectors = shafts.map(
    ({ vector, from, tip, head, body, ux, uy, desired }, index): VectorLayout => {
      const placement = outcome.get(`vector:${index}`);
      const box = placement?.boxes[0];
      const plan = vectorLabelPlans[index];
      return {
        vector,
        from,
        tip,
        head,
        body,
        label: box && vector.label ? placedLabel(vector.label, box) : null,
        ride:
          body === null
            ? null
            : {
                ux,
                uy,
                desired,
                labelWidth: plan?.labelWidth ?? 0,
                mid: plan?.mid ?? false,
                side: plan?.side ?? 1,
                beside: [0, 1, -1][placement?.home ?? 0] ?? 0,
                dx: placement?.dx ?? 0,
                dy: placement?.dy ?? 0,
              },
      };
    },
  );
  const angles = angleShapes.map((shape, index): AngleLayout => {
    const box = outcome.get(`angle:${index}`)?.boxes[0];
    return {
      ...shape,
      label: box && shape.angle.label ? placedLabel(shape.angle.label, box) : null,
    };
  });
  const arrowLabels = derived.flatMap(({ body, kind }, index): ArrowLabelLayout[] => {
    const text = spec.arrowLabels[kind];
    const nudge = outcome.get(`derived:${index}`);
    return text && nudge
      ? [
          {
            body,
            kind,
            text,
            width: measureText(text),
            beside: [0, 1, -1][nudge.home] ?? 0,
            dx: nudge.dx,
            dy: nudge.dy,
          },
        ]
      : [];
  });

  const strobes = spec.bodies.map((body, index) =>
    isStationary(body)
      ? []
      : strobeIndices(body.path.length, spec.strobe).map((i) => tracks[index][i]),
  );

  return {
    radii,
    boxAngles,
    tracks,
    closed,
    maxSpeed,
    floorY,
    obstacles,
    vectors,
    bodyLabels,
    angles,
    arrowLabels,
    solids,
    planet,
    tethers,
    pulley,
    restLines,
    strobes,
  };
}

// --- description -------------------------------------------------------------

type Translate = (key: string, options?: Record<string, unknown>) => string;

/**
 * What a screen reader hears for the scene when the server sent no `alt`: its
 * title, its bodies, the arrows it derives and the labels the solver stated —
 * the same facts the picture shows, in the order a sighted reader takes them in.
 */
export function describeSimulation(spec: SimulationSpec, t: Translate): string {
  const sentences: string[] = [sceneTitle(spec, t)];
  if (spec.bodies.length > 0) {
    sentences.push(
      spec.bodies.map((body) => body.label ?? t("rich.simulation_a11y_body")).join(", "),
    );
  }
  if (spec.inclineDeg !== undefined) {
    sentences.push(t("rich.simulation_a11y_slope", { degrees: Math.round(spec.inclineDeg) }));
  }
  if (spec.arrows.length > 0) {
    const names = spec.arrows.map((arrow) => {
      const name = t(`rich.simulation_arrow_${arrow}`);
      const label = spec.arrowLabels[arrow];
      return label ? `${name} ${label}` : name;
    });
    sentences.push(t("rich.simulation_a11y_arrows", { list: names.join(", ") }));
  }
  const labels = [
    ...spec.vectors.flatMap((vector) => (vector.label ? [vector.label] : [])),
    ...spec.angles.flatMap((angle) => (angle.label ? [angle.label] : [])),
  ];
  if (labels.length > 0) sentences.push(labels.join(", "));
  return sentences.map((sentence) => sentence.replace(/[.\s]+$/, "")).join(". ") + ".";
}

/** The canvas's accessibility label: the server's sentence when it sent one. */
export function simulationAccessibilityLabel(spec: SimulationSpec, t: Translate): string {
  return spec.alt ?? describeSimulation(spec, t);
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
  const yAt = (x: number) => onSurface.y + (x - onSurface.x) * slope;
  let x1 = spec.xMin;
  let x2 = spec.xMax;
  // With a ground line the slope ends where it meets the ground, as a wedge
  // does, instead of carrying on beneath the floor.
  if (spec.ground && slope !== 0) {
    const meets = onSurface.x - onSurface.y / slope;
    if (slope < 0) x2 = Math.min(x2, Math.max(x1, meets));
    else x1 = Math.max(x1, Math.min(x2, meets));
  }
  const left = worldToScreen(x1, yAt(x1), t);
  const right = worldToScreen(x2, yAt(x2), t);
  return { x1: left.px, y1: left.py, x2: right.px, y2: right.py };
}

/**
 * The wedge under a slope that stands on the ground: the triangle between the
 * surface, the ground line and the scene's edge, in screen points. Null
 * without a ground line, or when the surface never rises above it.
 */
export function inclineWedge(spec: SimulationSpec, t: SimulationTransform): ScreenPoint[] | null {
  if (!spec.ground) return null;
  const surface = inclineSurface(spec, t);
  if (!surface) return null;
  const floor = worldToScreen(0, 0, t).py;
  const high =
    surface.y1 < surface.y2
      ? { px: surface.x1, py: surface.y1 }
      : { px: surface.x2, py: surface.y2 };
  const low =
    surface.y1 < surface.y2
      ? { px: surface.x2, py: surface.y2 }
      : { px: surface.x1, py: surface.y1 };
  // Something to fill: the high end above the floor, the low end on it.
  if (!(high.py < floor - 0.5) || Math.abs(low.py - floor) > 0.5) return null;
  return [high, low, { px: high.px, py: floor }];
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
