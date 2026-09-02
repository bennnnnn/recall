export type RectangleSpec = {
  type: "rectangle" | "square";
  width: number;
  height: number;
  unit?: string;
  show_diagonal?: boolean;
  show_angle?: boolean;
  show_area?: boolean;
  show_perimeter?: boolean;
  /** School-diagram congruence ticks on equal sides (default on). */
  show_ticks?: boolean;
  diagonal?: number;
  angle_deg?: number;
  area?: number;
  perimeter?: number;
  labels?: Record<string, string>;
};

export type TriangleSpec = {
  type: "triangle";
  base: number;
  height: number;
  unit?: string;
  show_labels?: boolean;
  /** Congruence tick marks on equal legs (default on). */
  show_ticks?: boolean;
  /** Dashed altitude from apex to base (default on — already the height line). */
  show_altitude?: boolean;
  /** Interior vertex degrees (default on). */
  show_angle?: boolean;
  area?: number;
  labels?: Record<string, string>;
};

export type RightTriangleSpec = {
  type: "right_triangle";
  base: number;
  height: number;
  unit?: string;
  show_labels?: boolean;
  show_hypotenuse?: boolean;
  /** Interior vertex degrees, not only the 90° square (default on). */
  show_angle?: boolean;
  hypotenuse?: number;
  area?: number;
  labels?: Record<string, string>;
};

export type CircleSpec = {
  type: "circle";
  radius: number;
  unit?: string;
  show_labels?: boolean;
  show_diameter?: boolean;
  show_area?: boolean;
  show_circumference?: boolean;
  diameter?: number;
  area?: number;
  circumference?: number;
  labels?: Record<string, string>;
};

export type TriangleSidesSpec = {
  type: "triangle_sides";
  a: number;
  b: number;
  c: number;
  unit?: string;
  show_labels?: boolean;
  /** Congruence ticks on equal sides (default on when any sides match). */
  show_ticks?: boolean;
  /** Altitude from the apex (opp. side a) to side a (default on). */
  show_altitude?: boolean;
  /** Median from the apex to the midpoint of side a (default off; on for isosceles). */
  show_median?: boolean;
  show_angle?: boolean;
  area?: number;
  labels?: Record<string, string>;
};

export type TrapezoidSpec = {
  type: "trapezoid";
  top: number;
  bottom: number;
  height: number;
  unit?: string;
  show_labels?: boolean;
  show_angle?: boolean;
  area?: number;
  labels?: Record<string, string>;
};

export type ParallelogramSpec = {
  type: "parallelogram";
  base: number;
  height: number;
  side: number;
  unit?: string;
  show_labels?: boolean;
  show_angle?: boolean;
  area?: number;
  perimeter?: number;
  labels?: Record<string, string>;
};

export type SectorSpec = {
  type: "sector";
  radius: number;
  angle_deg: number;
  unit?: string;
  show_labels?: boolean;
  arc_length?: number;
  area?: number;
  labels?: Record<string, string>;
};

export type GeometrySpec =
  | RectangleSpec
  | TriangleSpec
  | RightTriangleSpec
  | CircleSpec
  | TriangleSidesSpec
  | TrapezoidSpec
  | ParallelogramSpec
  | SectorSpec;

/** Match backend `RectangleGeometryInput` / triangle inputs (`le=1_000_000`). */
export const MAX_GEOMETRY_DIMENSION = 1_000_000;

const RECTANGLE_TYPES = new Set(["rectangle", "rect", "square"]);

function readLabels(row: Record<string, unknown>): Record<string, string> | undefined {
  if (row.labels && typeof row.labels === "object") {
    return row.labels as Record<string, string>;
  }
  return undefined;
}

function readPositive(row: Record<string, unknown>, ...keys: string[]): number | null {
  for (const key of keys) {
    const value = Number(row[key]);
    if (Number.isFinite(value) && value > 0 && value <= MAX_GEOMETRY_DIMENSION) return value;
  }
  return null;
}

/** Copy an explicit JSON boolean (true or false). Skipping `false` made
 * `show_labels: false` (and similar) a no-op because renderers treat
 * `undefined` as "show". */
function copyFlag<T extends object>(spec: T, row: Record<string, unknown>, key: keyof T & string): void {
  if (row[key] === true || row[key] === false) {
    (spec as Record<string, unknown>)[key] = row[key];
  }
}

function parseRectangle(row: Record<string, unknown>): RectangleSpec | null {
  const rawType = String(row.type ?? "").trim().toLowerCase();
  if (!RECTANGLE_TYPES.has(rawType)) return null;

  const isSquare = rawType === "square";
  const side = readPositive(row, "side", "s");
  let width = readPositive(row, "width", "w", "length", "l");
  let height = readPositive(row, "height", "h", "breadth", "b");

  if (isSquare) {
    const edge = side ?? width ?? height;
    if (!edge) return null;
    width = edge;
    height = edge;
  } else if (!width || !height) {
    return null;
  }

  const spec: RectangleSpec = {
    type: isSquare ? "square" : "rectangle",
    width,
    height,
  };
  const unit = String(row.unit ?? "cm").trim();
  if (unit) spec.unit = unit;
  copyFlag(spec, row, "show_diagonal");
  copyFlag(spec, row, "show_angle");
  copyFlag(spec, row, "show_area");
  copyFlag(spec, row, "show_perimeter");
  copyFlag(spec, row, "show_ticks");
  const diagonal = Number(row.diagonal);
  if (Number.isFinite(diagonal)) spec.diagonal = diagonal;
  const angle = Number(row.angle_deg);
  if (Number.isFinite(angle)) spec.angle_deg = angle;
  const area = Number(row.area);
  if (Number.isFinite(area)) spec.area = area;
  const perimeter = Number(row.perimeter);
  if (Number.isFinite(perimeter)) spec.perimeter = perimeter;
  spec.labels = readLabels(row);
  return spec;
}

function parseTriangle(row: Record<string, unknown>): TriangleSpec | null {
  if (row.type !== "triangle") return null;
  const base = Number(row.base);
  const height = Number(row.height);
  if (
    !Number.isFinite(base) ||
    !Number.isFinite(height) ||
    base <= 0 ||
    height <= 0 ||
    base > MAX_GEOMETRY_DIMENSION ||
    height > MAX_GEOMETRY_DIMENSION
  ) {
    return null;
  }
  const spec: TriangleSpec = { type: "triangle", base, height };
  const unit = String(row.unit ?? "cm").trim();
  if (unit) spec.unit = unit;
  copyFlag(spec, row, "show_labels");
  copyFlag(spec, row, "show_ticks");
  copyFlag(spec, row, "show_altitude");
  copyFlag(spec, row, "show_angle");
  const area = Number(row.area);
  if (Number.isFinite(area)) spec.area = area;
  spec.labels = readLabels(row);
  return spec;
}

function parseRightTriangle(row: Record<string, unknown>): RightTriangleSpec | null {
  if (row.type !== "right_triangle") return null;
  const base = Number(row.base);
  const height = Number(row.height);
  if (
    !Number.isFinite(base) ||
    !Number.isFinite(height) ||
    base <= 0 ||
    height <= 0 ||
    base > MAX_GEOMETRY_DIMENSION ||
    height > MAX_GEOMETRY_DIMENSION
  ) {
    return null;
  }
  const spec: RightTriangleSpec = { type: "right_triangle", base, height };
  const unit = String(row.unit ?? "cm").trim();
  if (unit) spec.unit = unit;
  copyFlag(spec, row, "show_labels");
  copyFlag(spec, row, "show_hypotenuse");
  copyFlag(spec, row, "show_angle");
  const hypotenuse = Number(row.hypotenuse);
  if (Number.isFinite(hypotenuse)) spec.hypotenuse = hypotenuse;
  const area = Number(row.area);
  if (Number.isFinite(area)) spec.area = area;
  spec.labels = readLabels(row);
  return spec;
}

function parseCircle(row: Record<string, unknown>): CircleSpec | null {
  if (row.type !== "circle") return null;
  const radius = readPositive(row, "radius", "r");
  if (!radius) return null;

  const spec: CircleSpec = { type: "circle", radius };
  const unit = String(row.unit ?? "cm").trim();
  if (unit) spec.unit = unit;
  copyFlag(spec, row, "show_labels");
  copyFlag(spec, row, "show_diameter");
  copyFlag(spec, row, "show_area");
  copyFlag(spec, row, "show_circumference");
  const diameter = Number(row.diameter);
  if (Number.isFinite(diameter)) spec.diameter = diameter;
  const area = Number(row.area);
  if (Number.isFinite(area)) spec.area = area;
  const circumference = Number(row.circumference);
  if (Number.isFinite(circumference)) spec.circumference = circumference;
  spec.labels = readLabels(row);
  return spec;
}

function parseTriangleSides(row: Record<string, unknown>): TriangleSidesSpec | null {
  if (row.type !== "triangle_sides") return null;
  const a = readPositive(row, "a");
  const b = readPositive(row, "b");
  const c = readPositive(row, "c");
  if (!a || !b || !c) return null;
  if (a + b <= c || a + c <= b || b + c <= a) return null;
  const spec: TriangleSidesSpec = { type: "triangle_sides", a, b, c };
  const unit = String(row.unit ?? "cm").trim();
  if (unit) spec.unit = unit;
  copyFlag(spec, row, "show_labels");
  copyFlag(spec, row, "show_ticks");
  copyFlag(spec, row, "show_altitude");
  copyFlag(spec, row, "show_median");
  copyFlag(spec, row, "show_angle");
  const area = Number(row.area);
  if (Number.isFinite(area)) spec.area = area;
  spec.labels = readLabels(row);
  return spec;
}

function parseTrapezoid(row: Record<string, unknown>): TrapezoidSpec | null {
  if (row.type !== "trapezoid") return null;
  const top = readPositive(row, "top");
  const bottom = readPositive(row, "bottom");
  const height = readPositive(row, "height");
  if (!top || !bottom || !height) return null;
  const spec: TrapezoidSpec = { type: "trapezoid", top, bottom, height };
  const unit = String(row.unit ?? "cm").trim();
  if (unit) spec.unit = unit;
  copyFlag(spec, row, "show_labels");
  copyFlag(spec, row, "show_angle");
  const area = Number(row.area);
  if (Number.isFinite(area)) spec.area = area;
  spec.labels = readLabels(row);
  return spec;
}

function parseParallelogram(row: Record<string, unknown>): ParallelogramSpec | null {
  if (row.type !== "parallelogram") return null;
  const base = readPositive(row, "base");
  const height = readPositive(row, "height");
  const side = readPositive(row, "side");
  if (!base || !height || !side) return null;
  // The slant side is the hypotenuse of the right triangle formed by the
  // height, so it can never be shorter — guards the shear-offset math in
  // ParallelogramDiagram (sqrt of a negative number) against a malformed fence.
  if (side < height) return null;
  const spec: ParallelogramSpec = { type: "parallelogram", base, height, side };
  const unit = String(row.unit ?? "cm").trim();
  if (unit) spec.unit = unit;
  copyFlag(spec, row, "show_labels");
  copyFlag(spec, row, "show_angle");
  const area = Number(row.area);
  if (Number.isFinite(area)) spec.area = area;
  const perimeter = Number(row.perimeter);
  if (Number.isFinite(perimeter)) spec.perimeter = perimeter;
  spec.labels = readLabels(row);
  return spec;
}

function parseSector(row: Record<string, unknown>): SectorSpec | null {
  if (row.type !== "sector") return null;
  const radius = readPositive(row, "radius", "r");
  const angleRaw = Number(row.angle_deg);
  if (!radius || !Number.isFinite(angleRaw) || angleRaw <= 0 || angleRaw > 360) return null;
  const spec: SectorSpec = { type: "sector", radius, angle_deg: angleRaw };
  const unit = String(row.unit ?? "cm").trim();
  if (unit) spec.unit = unit;
  copyFlag(spec, row, "show_labels");
  const arcLength = Number(row.arc_length);
  if (Number.isFinite(arcLength)) spec.arc_length = arcLength;
  const area = Number(row.area);
  if (Number.isFinite(area)) spec.area = area;
  spec.labels = readLabels(row);
  return spec;
}

export function parseGeometrySpec(raw: string): GeometrySpec | null {
  try {
    const data = JSON.parse(raw.trim()) as unknown;
    if (!data || typeof data !== "object") return null;
    const row = data as Record<string, unknown>;
    return (
      parseRectangle(row) ??
      parseTriangle(row) ??
      parseRightTriangle(row) ??
      parseCircle(row) ??
      parseTriangleSides(row) ??
      parseTrapezoid(row) ??
      parseParallelogram(row) ??
      parseSector(row)
    );
  } catch {
    return null;
  }
}

export function computeRectangleLabels(spec: RectangleSpec): Record<string, string> {
  const unit = spec.unit ?? "cm";
  const diagonal =
    spec.diagonal ?? Math.sqrt(spec.width * spec.width + spec.height * spec.height);
  const angle = spec.angle_deg ?? (Math.atan2(spec.height, spec.width) * 180) / Math.PI;
  const area = spec.area ?? spec.width * spec.height;
  const perimeter = spec.perimeter ?? 2 * (spec.width + spec.height);
  const sideLabel = spec.labels?.side ?? `${spec.width} ${unit}`;
  return {
    width: spec.labels?.width ?? `${spec.width} ${unit}`,
    height: spec.labels?.height ?? `${spec.height} ${unit}`,
    side: sideLabel,
    diagonal: spec.labels?.diagonal ?? `${diagonal.toFixed(2)} ${unit}`,
    angle: spec.labels?.angle ?? `${angle.toFixed(1)}°`,
    area: spec.labels?.area ?? `${area % 1 === 0 ? area : area.toFixed(1)} ${unit}²`,
    perimeter: spec.labels?.perimeter ?? `${perimeter % 1 === 0 ? perimeter : perimeter.toFixed(1)} ${unit}`,
  };
}

export function computeTriangleLabels(spec: TriangleSpec): Record<string, string> {
  const unit = spec.unit ?? "cm";
  const area = spec.area ?? 0.5 * spec.base * spec.height;
  return {
    base: spec.labels?.base ?? `${spec.base} ${unit}`,
    height: spec.labels?.height ?? `${spec.height} ${unit}`,
    area: spec.labels?.area ?? `${area % 1 === 0 ? area : area.toFixed(1)} ${unit}²`,
  };
}

export function computeRightTriangleLabels(spec: RightTriangleSpec): Record<string, string> {
  const unit = spec.unit ?? "cm";
  const area = spec.area ?? 0.5 * spec.base * spec.height;
  const hypotenuse = spec.hypotenuse ?? Math.sqrt(spec.base * spec.base + spec.height * spec.height);
  const angleAtBase = (Math.atan2(spec.height, spec.base) * 180) / Math.PI;
  const angleAtHeight = (Math.atan2(spec.base, spec.height) * 180) / Math.PI;
  return {
    base: spec.labels?.base ?? `${spec.base} ${unit}`,
    height: spec.labels?.height ?? `${spec.height} ${unit}`,
    hypotenuse: spec.labels?.hypotenuse ?? `${hypotenuse % 1 === 0 ? hypotenuse : hypotenuse.toFixed(2)} ${unit}`,
    area: spec.labels?.area ?? `${area % 1 === 0 ? area : area.toFixed(1)} ${unit}²`,
    angle: spec.labels?.angle ?? "90°",
    angle_at_base: spec.labels?.angle_at_base ?? formatAngleDeg(angleAtBase),
    angle_at_height: spec.labels?.angle_at_height ?? formatAngleDeg(angleAtHeight),
  };
}

export function computeCircleLabels(spec: CircleSpec): Record<string, string> {
  const unit = spec.unit ?? "cm";
  const diameter = spec.diameter ?? spec.radius * 2;
  const area = spec.area ?? Math.PI * spec.radius * spec.radius;
  const circumference = spec.circumference ?? 2 * Math.PI * spec.radius;
  return {
    radius: spec.labels?.radius ?? `${spec.radius} ${unit}`,
    diameter: spec.labels?.diameter ?? `${diameter % 1 === 0 ? diameter : diameter.toFixed(2)} ${unit}`,
    area: spec.labels?.area ?? `${area.toFixed(2)} ${unit}²`,
    circumference: spec.labels?.circumference ?? `${circumference.toFixed(2)} ${unit}`,
  };
}

export function computeTriangleSidesLabels(spec: TriangleSidesSpec): Record<string, string> {
  const unit = spec.unit ?? "cm";
  const s = (spec.a + spec.b + spec.c) / 2;
  const area = spec.area ?? Math.sqrt(s * (s - spec.a) * (s - spec.b) * (s - spec.c));
  return {
    a: spec.labels?.a ?? `${spec.a} ${unit}`,
    b: spec.labels?.b ?? `${spec.b} ${unit}`,
    c: spec.labels?.c ?? `${spec.c} ${unit}`,
    area: spec.labels?.area ?? `${area % 1 === 0 ? area : area.toFixed(2)} ${unit}²`,
  };
}

/** Vertices for a triangle drawn from its three side lengths — side `a` laid
 * flat on the x-axis, the third vertex placed via the law of cosines. Callers
 * scale/translate the returned unit-ish coordinates to fit the SVG canvas. */
export function triangleSidesVertices(
  a: number,
  b: number,
  c: number,
): { x0: number; y0: number; x1: number; y1: number; x2: number; y2: number } {
  const cx = (b * b + a * a - c * c) / (2 * a);
  const cy = Math.sqrt(Math.max(0, b * b - cx * cx));
  return { x0: 0, y0: 0, x1: a, y1: 0, x2: cx, y2: cy };
}

/** Apex sits at a quarter of the base so a base+height triangle is scalene,
 * not an implied isosceles with equal-leg ticks. */
export const BASE_HEIGHT_APEX_T = 0.25;

export function baseHeightTriangleVertices(
  base: number,
  height: number,
): { x0: number; y0: number; x1: number; y1: number; x2: number; y2: number } {
  return {
    x0: 0,
    y0: height,
    x1: base,
    y1: height,
    x2: base * BASE_HEIGHT_APEX_T,
    y2: 0,
  };
}

export type TickSegment = { x1: number; y1: number; x2: number; y2: number };

/**
 * Congruence hash marks at the midpoint of a side, perpendicular to it.
 * `count` is the number of parallel ticks (1 / 2 / 3 for distinct equal groups).
 */
export function sideTickMarks(
  x1: number,
  y1: number,
  x2: number,
  y2: number,
  count: number,
  halfLen = 5,
  spacing = 4,
): TickSegment[] {
  if (count <= 0) return [];
  const dx = x2 - x1;
  const dy = y2 - y1;
  const len = Math.hypot(dx, dy) || 1;
  const ux = dx / len;
  const uy = dy / len;
  const px = -uy;
  const py = ux;
  const mx = (x1 + x2) / 2;
  const my = (y1 + y2) / 2;
  const start = -((count - 1) / 2) * spacing;
  const marks: TickSegment[] = [];
  for (let i = 0; i < count; i++) {
    const ox = mx + ux * (start + i * spacing);
    const oy = my + uy * (start + i * spacing);
    marks.push({
      x1: ox - px * halfLen,
      y1: oy - py * halfLen,
      x2: ox + px * halfLen,
      y2: oy + py * halfLen,
    });
  }
  return marks;
}

/** Tick counts for triangle sides a/b/c — 0 when unique, else 1/2/3 by equal-length group. */
export function equalSideTickCounts(
  a: number,
  b: number,
  c: number,
  eps = 1e-6,
): { a: number; b: number; c: number } {
  const sides: Array<{ key: "a" | "b" | "c"; len: number }> = [
    { key: "a", len: a },
    { key: "b", len: b },
    { key: "c", len: c },
  ];
  const used = new Set<"a" | "b" | "c">();
  const out = { a: 0, b: 0, c: 0 };
  let groupMark = 1;
  for (const side of sides) {
    if (used.has(side.key)) continue;
    const group = sides.filter((other) => Math.abs(other.len - side.len) <= eps);
    if (group.length < 2) {
      used.add(side.key);
      continue;
    }
    for (const member of group) {
      out[member.key] = groupMark;
      used.add(member.key);
    }
    groupMark += 1;
  }
  return out;
}

/** Foot of the perpendicular from C onto the line through A–B (not clamped). */
export function footOfPerpendicular(
  ax: number,
  ay: number,
  bx: number,
  by: number,
  cx: number,
  cy: number,
): { x: number; y: number } {
  const abx = bx - ax;
  const aby = by - ay;
  const ab2 = abx * abx + aby * aby || 1;
  const t = ((cx - ax) * abx + (cy - ay) * aby) / ab2;
  return { x: ax + t * abx, y: ay + t * aby };
}

export function midpoint(ax: number, ay: number, bx: number, by: number): { x: number; y: number } {
  return { x: (ax + bx) / 2, y: (ay + by) / 2 };
}

/** True when two of the three sides match (isosceles, including equilateral). */
export function isIsoscelesSides(a: number, b: number, c: number, eps = 1e-6): boolean {
  return (
    Math.abs(a - b) <= eps || Math.abs(a - c) <= eps || Math.abs(b - c) <= eps
  );
}

/** Whether congruence ticks should render (explicit flag, else default on). */
export function shouldShowTicks(showTicks: boolean | undefined, defaultOn = true): boolean {
  if (showTicks === false) return false;
  if (showTicks === true) return true;
  return defaultOn;
}

export function computeTrapezoidLabels(spec: TrapezoidSpec): Record<string, string> {
  const unit = spec.unit ?? "cm";
  const area = spec.area ?? ((spec.top + spec.bottom) / 2) * spec.height;
  return {
    top: spec.labels?.top ?? `${spec.top} ${unit}`,
    bottom: spec.labels?.bottom ?? `${spec.bottom} ${unit}`,
    height: spec.labels?.height ?? `${spec.height} ${unit}`,
    area: spec.labels?.area ?? `${area % 1 === 0 ? area : area.toFixed(1)} ${unit}²`,
  };
}

export function computeParallelogramLabels(spec: ParallelogramSpec): Record<string, string> {
  const unit = spec.unit ?? "cm";
  const area = spec.area ?? spec.base * spec.height;
  const perimeter = spec.perimeter ?? 2 * (spec.base + spec.side);
  return {
    base: spec.labels?.base ?? `${spec.base} ${unit}`,
    height: spec.labels?.height ?? `${spec.height} ${unit}`,
    side: spec.labels?.side ?? `${spec.side} ${unit}`,
    area: spec.labels?.area ?? `${area % 1 === 0 ? area : area.toFixed(1)} ${unit}²`,
    perimeter: spec.labels?.perimeter ?? `${perimeter % 1 === 0 ? perimeter : perimeter.toFixed(1)} ${unit}`,
  };
}

export function computeSectorLabels(spec: SectorSpec): Record<string, string> {
  const unit = spec.unit ?? "cm";
  const rad = (spec.angle_deg * Math.PI) / 180;
  const arcLength = spec.arc_length ?? spec.radius * rad;
  const area = spec.area ?? 0.5 * spec.radius * spec.radius * rad;
  return {
    radius: spec.labels?.radius ?? `${spec.radius} ${unit}`,
    angle: spec.labels?.angle ?? `${spec.angle_deg}°`,
    arc_length: spec.labels?.arc_length ?? `${arcLength.toFixed(2)} ${unit}`,
    area: spec.labels?.area ?? `${area.toFixed(2)} ${unit}²`,
  };
}

/**
 * Which angle-related elements a rectangle diagram should render. A
 * rectangle's own corners are always 90° — the right-angle bracket glyph is
 * the conventional way to say that. The diagonal-vs-base angle (`angle_deg`
 * in the spec) is a *different*, generally non-90° quantity, so it must
 * never be drawn at the same spot as that bracket — labeling it right next
 * to a glyph that means "90°" reads as a contradiction (e.g. a bracket next
 * to "51.3°"). Only show the diagonal's angle when a diagonal is actually
 * being drawn; suppress the bracket in that case since the angle of
 * interest there isn't the corner's.
 */
export function rectangleAngleDisplay(spec: {
  type: "rectangle" | "square";
  show_angle?: boolean;
  show_diagonal?: boolean;
}): { showCornerBracket: boolean; showDiagonalAngleLabel: boolean } {
  const isSquare = spec.type === "square";
  const showAngle = !!spec.show_angle;
  const showDiagonal = !!spec.show_diagonal;
  return {
    showCornerBracket: isSquare || (showAngle && !showDiagonal),
    showDiagonalAngleLabel: !isSquare && showAngle && showDiagonal,
  };
}

/**
 * SVG path for a small arc at the top-left corner of a rectangle, from the
 * top edge toward the TL→BR diagonal. Encodes the same diagonal-vs-base
 * angle shown as `∠ N°` text — a curved mark so the angle reads as a
 * school-diagram cue, not a bare floating number.
 *
 * Coordinates use SVG's y-down convention (`atan2(height, width)`).
 */
export function diagonalAngleArcPath(
  originX: number,
  originY: number,
  width: number,
  height: number,
  radius = 18,
): string {
  const w = Math.max(width, 1e-6);
  const h = Math.max(height, 1e-6);
  const theta = Math.atan2(h, w);
  const r = Math.min(radius, w * 0.28, h * 0.28);
  const x1 = originX + r;
  const y1 = originY;
  const x2 = originX + r * Math.cos(theta);
  const y2 = originY + r * Math.sin(theta);
  // sweep-flag 1 = clockwise in SVG → from +x down into the diagonal.
  return `M ${x1} ${y1} A ${r} ${r} 0 0 1 ${x2} ${y2}`;
}

export type AngleLeader = {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
};

export type VertexAngleMark = {
  path: string;
  labelX: number;
  labelY: number;
  text: string;
  deg: number;
  labelWidth: number;
  labelHeight: number;
  leader: AngleLeader | null;
};

const ANGLE_LABEL_FONT = 11;
const RIGHT_ANGLE_SQUARE = 14;

/** Backdrop size so `.5°` is not sitting on a stroke. */
export function estimateAngleLabelSize(text: string): { width: number; height: number } {
  return { width: Math.max(24, text.length * 6.6 + 10), height: ANGLE_LABEL_FONT + 7 };
}

function closestPointOnRect(
  px: number,
  py: number,
  cx: number,
  cy: number,
  w: number,
  h: number,
): { x: number; y: number } {
  return {
    x: Math.max(cx - w / 2, Math.min(cx + w / 2, px)),
    y: Math.max(cy - h / 2, Math.min(cy + h / 2, py)),
  };
}

/** School-diagram degree label: `90°` / `36.9°`. */
export function formatAngleDeg(deg: number): string {
  const rounded = Math.round(deg * 10) / 10;
  if (Math.abs(rounded - Math.round(rounded)) < 0.05) {
    return `${Math.round(rounded)}°`;
  }
  return `${rounded.toFixed(1)}°`;
}

export function isRightAngleDeg(deg: number, tolerance = 0.6): boolean {
  return Math.abs(deg - 90) < tolerance;
}

/**
 * Interior angle at vertex B of triangle ABC (SVG y-down). The shorter arc
 * is the interior for convex polygons.
 */
export function vertexAngleMark(
  ax: number,
  ay: number,
  bx: number,
  by: number,
  cx: number,
  cy: number,
  radius = 16,
): VertexAngleMark {
  const a1 = Math.atan2(ay - by, ax - bx);
  const a2 = Math.atan2(cy - by, cx - bx);
  let delta = a2 - a1;
  while (delta > Math.PI) delta -= 2 * Math.PI;
  while (delta < -Math.PI) delta += 2 * Math.PI;
  const deg = (Math.abs(delta) * 180) / Math.PI;
  const r = Math.max(radius, 8);
  const x1 = bx + r * Math.cos(a1);
  const y1 = by + r * Math.sin(a1);
  const x2 = bx + r * Math.cos(a1 + delta);
  const y2 = by + r * Math.sin(a1 + delta);
  const sweep = delta > 0 ? 1 : 0;
  const mid = a1 + delta / 2;
  const text = formatAngleDeg(deg);
  const { width: labelWidth, height: labelHeight } = estimateAngleLabelSize(text);
  const half = Math.abs(delta) / 2;
  const fromWedge = (labelWidth / 2 + 5) / Math.sin(Math.max(half, 1e-3));
  const minSide = Math.min(Math.hypot(ax - bx, ay - by), Math.hypot(cx - bx, cy - by));
  const interiorR = Math.min(Math.max(r + 18, fromWedge), Math.max(minSide * 0.42, r + 18));
  const inX = bx + interiorR * Math.cos(mid);
  const inY = by + interiorR * Math.sin(mid);
  const right = isRightAngleDeg(deg);
  const wedgeW = 2 * interiorR * Math.sin(half);
  const overlapsSquare = right && interiorR < RIGHT_ANGLE_SQUARE + labelHeight / 2 + 8;
  const fitsInside =
    !overlapsSquare &&
    wedgeW >= labelWidth * 0.75 &&
    interiorR + labelHeight / 2 < minSide * 0.55;
  if (fitsInside) {
    return {
      path: `M ${x1} ${y1} A ${r} ${r} 0 0 ${sweep} ${x2} ${y2}`,
      labelX: inX,
      labelY: inY,
      text,
      deg,
      labelWidth,
      labelHeight,
      leader: null,
    };
  }
  const outR = Math.max(r + 22, 32 + Math.max(labelWidth, labelHeight) * 0.4);
  const labelX = bx + outR * Math.cos(mid + Math.PI);
  const labelY = by + outR * Math.sin(mid + Math.PI);
  const startX = bx + Math.min(r, 12) * Math.cos(mid);
  const startY = by + Math.min(r, 12) * Math.sin(mid);
  const end = closestPointOnRect(startX, startY, labelX, labelY, labelWidth, labelHeight);
  return {
    path: `M ${x1} ${y1} A ${r} ${r} 0 0 ${sweep} ${x2} ${y2}`,
    labelX,
    labelY,
    text,
    deg,
    labelWidth,
    labelHeight,
    leader: { x1: startX, y1: startY, x2: end.x, y2: end.y },
  };
}

/** Grow the SVG so exterior degree labels are not clipped. */
export function padDiagramForAngleLabels(
  vertices: { x: number; y: number }[],
  svgW: number,
  svgH: number,
  margin = 10,
): { vertices: { x: number; y: number }[]; svgW: number; svgH: number } {
  const marks = polygonInteriorAngleMarks(vertices);
  let minX = 0;
  let minY = 0;
  let maxX = svgW;
  let maxY = svgH;
  for (const m of marks) {
    minX = Math.min(minX, m.labelX - m.labelWidth / 2);
    minY = Math.min(minY, m.labelY - m.labelHeight / 2);
    maxX = Math.max(maxX, m.labelX + m.labelWidth / 2);
    maxY = Math.max(maxY, m.labelY + m.labelHeight / 2);
  }
  const dx = minX < margin ? margin - minX : 0;
  const dy = minY < margin ? margin - minY : 0;
  return {
    vertices: dx || dy ? vertices.map((v) => ({ x: v.x + dx, y: v.y + dy })) : vertices,
    svgW: maxX + dx + margin,
    svgH: maxY + dy + margin,
  };
}

export function polygonInteriorAngleMarks(
  vertices: { x: number; y: number }[],
  radius = 16,
): VertexAngleMark[] {
  const n = vertices.length;
  if (n < 3) return [];
  return vertices.map((b, i) => {
    const a = vertices[(i + n - 1) % n];
    const c = vertices[(i + 1) % n];
    return vertexAngleMark(a.x, a.y, b.x, b.y, c.x, c.y, radius);
  });
}

export function scaleToFit(
  width: number,
  height: number,
  maxWidth: number,
  padding = 80,
): { w: number; h: number; scale: number } {
  const inner = Math.max(maxWidth - padding, 120);
  const scale = inner / Math.max(width, height, 1);
  return { w: width * scale, h: height * scale, scale };
}

/** Horizontal span of a parallelogram: base plus the shear of the slanted side. */
export function parallelogramSpan(base: number, height: number, side: number): number {
  const shear = Math.sqrt(Math.max(0, side * side - height * height));
  return base + shear;
}

export type ParallelogramLayout = {
  b: number;
  h: number;
  s: number;
  shear: number;
  offsetX: number;
  offsetY: number;
  svgW: number;
  svgH: number;
  bx0: number;
  bx1: number;
  by: number;
  tx0: number;
  tx1: number;
  ty: number;
};

/**
 * Fit a parallelogram into the bubble. Scale against `base + shear` (the
 * drawn width), not `max(base, side)` — otherwise the SVG is ~1.5–2× too
 * wide and `alignItems: "center"` clips both slanted ends.
 */
export function parallelogramLayout(
  spec: Pick<ParallelogramSpec, "base" | "height" | "side">,
  screenWidth: number,
): ParallelogramLayout {
  const inner = Math.max(screenWidth - 48 - 80, 120);
  const span = parallelogramSpan(spec.base, spec.height, spec.side);
  const scale = inner / Math.max(span, spec.height, 1);
  const b = spec.base * scale;
  const h = spec.height * scale;
  const s = spec.side * scale;
  const shear = Math.sqrt(Math.max(0, s * s - h * h));
  const offsetX = 40 + shear;
  const offsetY = 28;
  // Leftmost point is tx0 = offsetX - shear = 40; rightmost is bx1 = offsetX + b.
  // Do not add shear again — offsetX already contains it.
  const svgW = b + shear + 80;
  const svgH = h + offsetY + 40;
  const bx0 = offsetX;
  const bx1 = offsetX + b;
  const by = offsetY + h;
  const tx0 = offsetX - shear;
  const tx1 = tx0 + b;
  const ty = offsetY;
  return { b, h, s, shear, offsetX, offsetY, svgW, svgH, bx0, bx1, by, tx0, tx1, ty };
}
