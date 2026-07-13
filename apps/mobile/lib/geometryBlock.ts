export type RectangleSpec = {
  type: "rectangle" | "square";
  width: number;
  height: number;
  unit?: string;
  show_diagonal?: boolean;
  show_angle?: boolean;
  show_area?: boolean;
  show_perimeter?: boolean;
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

export type GeometrySpec = RectangleSpec | TriangleSpec | RightTriangleSpec | CircleSpec;

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
  if (row.show_diagonal === true) spec.show_diagonal = true;
  if (row.show_angle === true) spec.show_angle = true;
  if (row.show_area === true) spec.show_area = true;
  if (row.show_perimeter === true) spec.show_perimeter = true;
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
  if (row.show_labels === true) spec.show_labels = true;
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
  if (row.show_labels === true) spec.show_labels = true;
  if (row.show_hypotenuse === true) spec.show_hypotenuse = true;
  if (row.show_angle === true) spec.show_angle = true;
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
  if (row.show_labels === true) spec.show_labels = true;
  if (row.show_diameter === true) spec.show_diameter = true;
  if (row.show_area === true) spec.show_area = true;
  if (row.show_circumference === true) spec.show_circumference = true;
  const diameter = Number(row.diameter);
  if (Number.isFinite(diameter)) spec.diameter = diameter;
  const area = Number(row.area);
  if (Number.isFinite(area)) spec.area = area;
  const circumference = Number(row.circumference);
  if (Number.isFinite(circumference)) spec.circumference = circumference;
  spec.labels = readLabels(row);
  return spec;
}

export function parseGeometrySpec(raw: string): GeometrySpec | null {
  try {
    const data = JSON.parse(raw.trim()) as unknown;
    if (!data || typeof data !== "object") return null;
    const row = data as Record<string, unknown>;
    return (
      parseRectangle(row) ?? parseTriangle(row) ?? parseRightTriangle(row) ?? parseCircle(row)
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
  return {
    base: spec.labels?.base ?? `${spec.base} ${unit}`,
    height: spec.labels?.height ?? `${spec.height} ${unit}`,
    hypotenuse: spec.labels?.hypotenuse ?? `${hypotenuse % 1 === 0 ? hypotenuse : hypotenuse.toFixed(2)} ${unit}`,
    area: spec.labels?.area ?? `${area % 1 === 0 ? area : area.toFixed(1)} ${unit}²`,
    angle: spec.labels?.angle ?? "90°",
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

/** @deprecated use scaleToFit */
export const scaleRectangle = scaleToFit;
