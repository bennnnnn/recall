/**
 * A ```graph `plot`: a graph the server drew from a checked picture description (curves,
 * tangents, asymptotes, points, shaded regions, Riemann rectangles, an axis of revolution).
 * Every coordinate and label is the server's (`app/modules/math/schemas/plot.py`); the phone
 * reads them, lays them out in pixels (`plotLayout`) and draws them, in Skia or SVG alike,
 * working nothing out. A part that is malformed is left out, never the graph.
 */
import { mapGraphPoint } from "@/lib/math/graphBlock";

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

const MAX_CURVES = 6;
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

type Px = { px: number; py: number };
export type PlotLabel = { x: number; y: number; text: string; anchor: "start" | "end" | "middle" };

export type PlotLayout = {
  bounds: PlotBounds;
  curves: { color: number; paths: Px[][] }[];
  lines: { from: Px; to: Px; role: PlotLineRole; color: number }[];
  regions: { points: Px[]; kind: PlotRegionKind; color: number }[];
  dots: { at: Px; open: boolean; color: number }[];
  labels: PlotLabel[];
  /** Where the axis of revolution's turning arrow sits. */
  turns: Px[];
  legend: { label: string; color: number; role: PlotLineRole | "curve" }[];
};

const LABEL_SIZE = 11;
/** A semibold 11pt label's advance per character, rounded up so labels never touch. */
const CHAR_PX = 6.8;
const LABEL_GAP = 6;

type Box = { x0: number; y0: number; x1: number; y1: number };

function overlaps(a: Box, b: Box): boolean {
  return a.x0 < b.x1 && b.x0 < a.x1 && a.y0 < b.y1 && b.y0 < a.y1;
}

/**
 * A label beside its point, in the first place around it that stays on the canvas and meets
 * no other label; none when every place does (the dot stays, its label left out, never set
 * over another's).
 */
function placeLabel(at: Px, label: string, taken: Box[], width: number, height: number): PlotLabel | null {
  const w = label.length * CHAR_PX;
  const places: [number, number, "start" | "end" | "middle"][] = [];
  for (const gap of [LABEL_GAP, LABEL_GAP * 2.5]) {
    places.push(
      [at.px + gap, at.py - gap, "start"],
      [at.px - gap, at.py - gap, "end"],
      [at.px + gap, at.py + gap + LABEL_SIZE, "start"],
      [at.px - gap, at.py + gap + LABEL_SIZE, "end"],
      [at.px, at.py - gap - 2, "middle"],
      [at.px, at.py + gap + LABEL_SIZE + 2, "middle"],
    );
  }
  const inside = (b: Box) => b.x0 >= 2 && b.x1 <= width - 2 && b.y0 >= 2 && b.y1 <= height - 2;
  for (const [x, y, anchor] of places) {
    const x0 = anchor === "start" ? x : anchor === "end" ? x - w : x - w / 2;
    const box = { x0, y0: y - LABEL_SIZE, x1: x0 + w, y1: y + 2 };
    if (inside(box) && !taken.some((t) => overlaps(t, box))) {
      taken.push(box);
      return { x, y, text: label, anchor };
    }
  }
  return null;
}

function inBounds(x: number, y: number, b: PlotBounds): boolean {
  return x >= b.xMin && x <= b.xMax && y >= b.yMin && y <= b.yMax;
}

/** Every part of the plot in pixels, for a canvas `width` by `height` inset by `pad`. */
export function plotLayout(graph: PlotGraph, width: number, height: number, pad: number): PlotLayout {
  const bounds = plotBounds(graph, width, height, pad);
  const at = ([x, y]: Pair) => mapGraphPoint(x, y, bounds, width, height, pad);
  const taken: Box[] = [];
  const labels: PlotLabel[] = [];
  const dots = graph.points
    .filter((p) => inBounds(p.x, p.y, bounds))
    .map((p) => {
      const spot = at([p.x, p.y]);
      const placed = p.label ? placeLabel(spot, p.label, taken, width, height) : null;
      if (placed) labels.push(placed);
      return { at: spot, open: p.open, color: p.color };
    });
  const lines = graph.lines.map((line) => ({
    from: at(line.start),
    to: at(line.end),
    role: line.role,
    color: line.color,
  }));
  for (const line of graph.lines) {
    if (line.role === "segment" && line.label) {
      const mid: Pair = [(line.start[0] + line.end[0]) / 2, (line.start[1] + line.end[1]) / 2];
      const placed = placeLabel(at(mid), line.label, taken, width, height);
      if (placed) labels.push(placed);
    }
  }
  const turns = graph.lines
    .filter((line) => line.role === "axis")
    .map((line) => {
      const end = at(line.end);
      return { px: Math.min(end.px, width - pad - 10), py: Math.max(end.py, pad + 10) };
    });
  const legend: PlotLayout["legend"] = [
    ...graph.curves.filter((c) => c.label).map((c) => ({ label: c.label, color: c.color, role: "curve" as const })),
    ...graph.lines
      .filter((l) => l.label && l.role !== "segment")
      .map((l) => ({ label: l.label, color: l.color, role: l.role })),
  ];
  return {
    bounds,
    curves: graph.curves.map((curve) => ({ color: curve.color, paths: curve.segments.map((s) => s.map(at)) })),
    lines,
    regions: graph.regions.map((region) => ({ points: region.points.map(at), kind: region.kind, color: region.color })),
    dots,
    labels,
    turns,
    legend,
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
