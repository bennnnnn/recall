/**
 * A ```graph `points` fence: lettered points the server read off the question, on a
 * coordinate plane it sized to hold them (`math/figure`). The phone draws them where
 * they are and never moves or computes one.
 */
import { parseJsonRecord } from "@/lib/fence/json";
import { MAX_GEOMETRY_DIMENSION } from "@/lib/math/geometryTypes";

type PlanePoint = { x: number; y: number; label: string };

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
};

const MAX_POINTS = 12;
const MAX_LABEL = 24;

function finite(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value) && Math.abs(value) <= MAX_GEOMETRY_DIMENSION;
}

function readPoint(raw: unknown): PlanePoint | null {
  if (!raw || typeof raw !== "object") return null;
  const row = raw as Record<string, unknown>;
  const label = typeof row.label === "string" ? row.label.trim().slice(0, MAX_LABEL) : "";
  if (!finite(row.x) || !finite(row.y) || !label) return null;
  return { x: row.x, y: row.y, label };
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
  return { type: "points", title, points: plotted, xMin, xMax, yMin, yMax, quadrants: row.quadrants === true };
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
