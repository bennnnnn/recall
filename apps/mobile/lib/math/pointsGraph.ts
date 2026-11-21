/**
 * A ```graph `points` fence: lettered points the server read off the question, on a
 * coordinate plane it sized to hold them (`math/figure`), with the segments, polygons,
 * circles and right-angle marks of coordinate geometry and a transformation's image the
 * server worked out (`math/figure/plane`). The phone draws them where they are and never
 * moves or computes one. A malformed part is left out, never the plane.
 */
import { parseJsonRecord } from "@/lib/fence/json";
import { MAX_GEOMETRY_DIMENSION } from "@/lib/math/geometryTypes";

/** The question's own shape, the image a transformation makes of it, or a guide line. */
export type PlaneRole = "shape" | "image" | "guide";
/** Where a point's label sits beside it, away from the rest of its shape. */
export type LabelSide = "ne" | "nw" | "se" | "sw";
type Pair = [number, number];

type PlanePoint = { x: number; y: number; label: string; role: PlaneRole; side: LabelSide };
type PlaneSegment = {
  start: Pair;
  end: Pair;
  label: string;
  role: PlaneRole;
  dashed: boolean;
  arrow: boolean;
  ticks: number;
};
type PlanePolygon = { points: Pair[]; role: PlaneRole };
type PlaneCircle = { center: Pair; radius: number; role: PlaneRole };
type PlaneRightAngle = { at: Pair; a: Pair; b: Pair };

export type PointsGraph = {
  type: "points";
  title: string;
  points: PlanePoint[];
  xMin: number;
  xMax: number;
  yMin: number;
  yMax: number;
  /** The quadrants' numerals, when the question asks which quadrant. */
  quadrants: boolean;
  segments: PlaneSegment[];
  polygons: PlanePolygon[];
  circles: PlaneCircle[];
  rightAngles: PlaneRightAngle[];
};

const MAX_POINTS = 12;
const MAX_LABEL = 24;
const MAX_SEGMENTS = 24;
const MAX_POLYGONS = 4;
const MAX_CORNERS = 12;
const MAX_CIRCLES = 2;
const MAX_RIGHT_ANGLES = 6;
const ROLES: readonly PlaneRole[] = ["shape", "image", "guide"];
const SIDES: readonly LabelSide[] = ["ne", "nw", "se", "sw"];

function finite(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value) && Math.abs(value) <= MAX_GEOMETRY_DIMENSION;
}

function role(raw: unknown): PlaneRole {
  return ROLES.find((r) => r === raw) ?? "shape";
}

function pair(raw: unknown): Pair | null {
  if (!Array.isArray(raw) || raw.length !== 2) return null;
  const [x, y] = raw;
  return finite(x) && finite(y) ? [x, y] : null;
}

function rows(raw: unknown, most: number): Record<string, unknown>[] {
  if (!Array.isArray(raw)) return [];
  return raw.slice(0, most).filter((row): row is Record<string, unknown> => !!row && typeof row === "object");
}

function readPoint(raw: unknown): PlanePoint | null {
  if (!raw || typeof raw !== "object") return null;
  const row = raw as Record<string, unknown>;
  const label = typeof row.label === "string" ? row.label.trim().slice(0, MAX_LABEL) : "";
  if (!finite(row.x) || !finite(row.y) || !label) return null;
  const side = SIDES.find((s) => s === row.side) ?? "ne";
  return { x: row.x, y: row.y, label, role: role(row.role), side };
}

function readSegments(raw: unknown): PlaneSegment[] {
  return rows(raw, MAX_SEGMENTS).flatMap((row) => {
    const start = pair(row.start);
    const end = pair(row.end);
    if (!start || !end) return [];
    const ticks = typeof row.ticks === "number" && Number.isInteger(row.ticks) ? Math.min(3, Math.max(0, row.ticks)) : 0;
    const label = typeof row.label === "string" ? row.label.trim().slice(0, MAX_LABEL) : "";
    return [{ start, end, label, role: role(row.role), dashed: row.dashed === true, arrow: row.arrow === true, ticks }];
  });
}

function readPolygons(raw: unknown): PlanePolygon[] {
  return rows(raw, MAX_POLYGONS).flatMap((row) => {
    const corners = Array.isArray(row.points) ? row.points.slice(0, MAX_CORNERS).map(pair) : [];
    if (corners.length < 3 || corners.some((corner) => corner === null)) return [];
    return [{ points: corners as Pair[], role: role(row.role) }];
  });
}

function readCircles(raw: unknown): PlaneCircle[] {
  return rows(raw, MAX_CIRCLES).flatMap((row) => {
    const center = pair(row.center);
    return center && finite(row.radius) && row.radius > 0 ? [{ center, radius: row.radius, role: role(row.role) }] : [];
  });
}

function readRightAngles(raw: unknown): PlaneRightAngle[] {
  return rows(raw, MAX_RIGHT_ANGLES).flatMap((row) => {
    const [at, a, b] = [pair(row.at), pair(row.a), pair(row.b)];
    return at && a && b ? [{ at, a, b }] : [];
  });
}

export function parsePointsGraph(raw: string): PointsGraph | null {
  const row = parseJsonRecord(raw.trim());
  if (!row || row.type !== "points" || !Array.isArray(row.points)) return null;
  const points = row.points.slice(0, MAX_POINTS).map(readPoint);
  if (!points.length || points.some((point) => point === null)) return null;
  const { x_min: xMin, x_max: xMax, y_min: yMin, y_max: yMax } = row;
  if (!finite(xMin) || !finite(xMax) || !finite(yMin) || !finite(yMax) || xMax <= xMin || yMax <= yMin) {
    return null;
  }
  const plotted = points as PlanePoint[];
  if (plotted.some((p) => p.x < xMin || p.x > xMax || p.y < yMin || p.y > yMax)) return null;
  const title = typeof row.title === "string" ? row.title.slice(0, 64) : "";
  return {
    type: "points",
    title,
    points: plotted,
    xMin,
    xMax,
    yMin,
    yMax,
    quadrants: row.quadrants === true,
    segments: readSegments(row.segments),
    polygons: readPolygons(row.polygons),
    circles: readCircles(row.circles),
    rightAngles: readRightAngles(row.right_angles),
  };
}

/** Each quadrant's numeral, at the middle of its quarter of the view. */
export function quadrantNumerals(graph: PointsGraph): { text: string; x: number; y: number }[] {
  const { xMin, xMax, yMin, yMax } = graph;
  if (!(xMin < 0 && xMax > 0 && yMin < 0 && yMax > 0)) return [];
  return [
    { text: "I", x: xMax / 2, y: yMax / 2 },
    { text: "II", x: xMin / 2, y: yMax / 2 },
    { text: "III", x: xMin / 2, y: yMin / 2 },
    { text: "IV", x: xMax / 2, y: yMin / 2 },
  ];
}

/** The tallest and the flattest a coordinate plane is drawn, as a share of its width. */
const MAX_ASPECT = 1.25;
const MIN_ASPECT = 0.5;

/**
 * The plane's height for ``width``: one unit as tall as it is wide while that keeps the
 * card a sensible shape; points far up one axis ((1, 60) to (3, 180)) stretch the other
 * instead of drawing a card 10,000 px tall or 47 px flat.
 */
export function pointsChartHeight(graph: PointsGraph, width: number, pad: number): number {
  const inner = Math.max(width - pad * 2, 1);
  const square = (graph.yMax - graph.yMin) / (graph.xMax - graph.xMin);
  return inner * Math.min(MAX_ASPECT, Math.max(MIN_ASPECT, square)) + pad * 2;
}
