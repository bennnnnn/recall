import {
  MAX_GEOMETRY_DIMENSION,
  type CircleSpec,
  type GeometrySpec,
  type ParallelogramSpec,
  type RectangleSpec,
  type RightTriangleSpec,
  type SectorSpec,
  type TrapezoidSpec,
  type TriangleSidesSpec,
  type TriangleSpec,
} from "@/lib/math/geometryTypes";

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
  copyFlag(spec, row, "relative_lengths");
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
  copyFlag(spec, row, "show_perimeter");
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
