/**
 * A ```graph `plot`: a graph the server drew from a checked picture description (curves,
 * tangents, asymptotes, points, shaded regions, Riemann rectangles, an axis of revolution).
 * Every coordinate and label is the server's (`app/modules/math/schemas/plot.py`); the phone
 * reads them and draws them with the function graph's own renderers
 * (`components/rich/plotDrawing`), in Skia or SVG alike, working nothing out. A part that is malformed is left out, never the graph.
 */
import { type GraphSpec } from "@/lib/math/graphSpec";

type Pair = [number, number];
export type PlotLineRole = "line" | "asymptote" | "axis" | "segment";
/** A shaded area; a Riemann rectangle or a solid's slice; the slice turned about its axis. */
export type PlotRegionKind = "shade" | "strip" | "mirror";

export type PlotGraph = {
  xMin: number;
  xMax: number;
  yMin: number;
  yMax: number;
  /** One unit as long on both axes (a normal drawn perpendicular, a distance true). */
  equal: boolean;
  xLabel: string;
  yLabel: string;
  curves: { label: string; segments: Pair[][]; color: number }[];
  lines: { start: Pair; end: Pair; role: PlotLineRole; label: string; color: number }[];
  regions: { points: Pair[]; kind: PlotRegionKind; color: number }[];
  points: { x: number; y: number; open: boolean; label: string; color: number }[];
};

const MAX_CURVES = 4;
const MAX_SEGMENTS = 24;
const MAX_SAMPLES = 800;
const MAX_LINES = 16;
const MAX_REGIONS = 48;
const MAX_REGION_POINTS = 600;
const MAX_POINTS = 24;
const MAX_LABEL = 48;
const ROLES: readonly PlotLineRole[] = ["line", "asymptote", "axis", "segment"];

function pair(raw: unknown): Pair | null {
  if (!Array.isArray(raw) || raw.length !== 2) return null;
  const [x, y] = raw;
  return typeof x === "number" && typeof y === "number" && Number.isFinite(x) && Number.isFinite(y)
    ? [x, y]
    : null;
}

function pairs(raw: unknown, most: number): Pair[] {
  if (!Array.isArray(raw)) return [];
  return raw.slice(0, most).map(pair).filter((p): p is Pair => p != null);
}

function rows(raw: unknown, most: number): Record<string, unknown>[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .slice(0, most)
    .filter((row): row is Record<string, unknown> => !!row && typeof row === "object");
}

function text(raw: unknown): string {
  return typeof raw === "string" ? raw.trim().slice(0, MAX_LABEL) : "";
}

function colorIndex(raw: unknown): number {
  return typeof raw === "number" && Number.isInteger(raw) && raw >= 0 && raw <= 5 ? raw : 0;
}

function finite(raw: unknown): number | null {
  return typeof raw === "number" && Number.isFinite(raw) ? raw : null;
}

/** The fence's plot, or null when it is not one this build can draw. */
export function parsePlotGraph(raw: string): PlotGraph | null {
  let data: unknown;
  try {
    data = JSON.parse(raw.trim());
  } catch {
    return null;
  }
  if (!data || typeof data !== "object") return null;
  const row = data as Record<string, unknown>;
  if (row.type !== "plot") return null;
  const [xMin, xMax, yMin, yMax] = [row.x_min, row.x_max, row.y_min, row.y_max].map(finite);
  if (xMin == null || xMax == null || yMin == null || yMax == null) return null;
  if (!(xMax > xMin) || !(yMax > yMin) || !Number.isFinite(xMax - xMin) || !Number.isFinite(yMax - yMin)) {
    return null;
  }
  const curves = rows(row.curves, MAX_CURVES)
    .map((curve) => ({
      label: text(curve.label),
      segments: (Array.isArray(curve.segments) ? curve.segments.slice(0, MAX_SEGMENTS) : [])
        .map((segment) => pairs(segment, MAX_SAMPLES))
        .filter((segment) => segment.length >= 2),
      color: colorIndex(curve.color),
    }))
    .filter((curve) => curve.segments.length > 0);
  if (!curves.length) return null;
  const lines = rows(row.lines, MAX_LINES).flatMap((line) => {
    const start = pair(line.start);
    const end = pair(line.end);
    const role = ROLES.find((r) => r === line.role) ?? "line";
    return start && end ? [{ start, end, role, label: text(line.label), color: colorIndex(line.color) }] : [];
  });
  const regions = rows(row.regions, MAX_REGIONS).flatMap((region) => {
    const points = pairs(region.points, MAX_REGION_POINTS);
    const kind: PlotRegionKind = region.kind === "strip" || region.kind === "mirror" ? region.kind : "shade";
    return points.length >= 3 ? [{ points, kind, color: colorIndex(region.color) }] : [];
  });
  const points = rows(row.points, MAX_POINTS).flatMap((point) => {
    const x = finite(point.x);
    const y = finite(point.y);
    return x != null && y != null
      ? [{ x, y, open: point.open === true, label: text(point.label), color: colorIndex(point.color) }]
      : [];
  });
  return {
    xMin, xMax, yMin, yMax,
    equal: row.equal === true,
    xLabel: text(row.x_label) || "x",
    yLabel: text(row.y_label) || "y",
    curves, lines, regions, points,
  };
}

export type PlotBounds = { xMin: number; xMax: number; yMin: number; yMax: number };

/** The server's window, grown on one axis to one scale when the plot asks for it. */
export function plotBounds(graph: PlotGraph, width: number, height: number, pad: number): PlotBounds {
  const bounds = { xMin: graph.xMin, xMax: graph.xMax, yMin: graph.yMin, yMax: graph.yMax };
  const aspect = (width - pad * 2) / Math.max(1, height - pad * 2);
  if (!graph.equal || !(aspect > 0)) return bounds;
  const wide = bounds.xMax - bounds.xMin;
  const tall = bounds.yMax - bounds.yMin;
  if (wide / tall > aspect) {
    const grow = (wide / aspect - tall) / 2;
    return { ...bounds, yMin: bounds.yMin - grow, yMax: bounds.yMax + grow };
  }
  const grow = (tall * aspect - wide) / 2;
  return { ...bounds, xMin: bounds.xMin - grow, xMax: bounds.xMax + grow };
}

/** What a function graph does not draw, a plot adds as layers: lines and regions. */
export type GraphLayers = {
  lines: { start: Pair; end: Pair; role: PlotLineRole; color: number }[];
  regions: { points: Pair[]; kind: PlotRegionKind; color: number }[];
};

/** The plot as a function graph's spec, for what its axes are named. */
export function plotAxes(graph: PlotGraph): GraphSpec {
  const first = graph.curves[0];
  return {
    type: "function",
    expr: first.label,
    points: first.segments.flat(),
    x_label: graph.xLabel,
    y_label: graph.yLabel,
  };
}

/** The plot's text for a screen reader: what its legend and labels say. */
export function plotDescription(graph: PlotGraph): string {
  const parts = [
    ...graph.curves.map((c) => c.label),
    ...graph.lines.map((l) => l.label),
    ...graph.points.map((p) => p.label),
  ].filter(Boolean);
  return parts.join(", ");
}
