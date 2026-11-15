/**
 * A server-drawn plot (`lib/math/plotGraph`) as the function graph's own renderers take it
 * (`GraphCanvas` in SVG, `SkiaGraphCanvas` in Skia): its curves as drawn series, its points
 * as holes and marks (a mark's label the server's, or none), its lines and regions as
 * layers, and the legend's rows.
 */
import { type GraphPoints } from "@/components/rich/graphPoints";
import { type DrawnSeries } from "@/hooks/useInteractiveGraph";
import { type GraphLayers, type PlotGraph, type PlotLineRole } from "@/lib/math/plotGraph";

export type PlotDrawing = {
  drawn: DrawnSeries[];
  points: GraphPoints;
  layers: GraphLayers;
  legend: { label: string; color: number; role: PlotLineRole | "curve" }[];
};

export function plotDrawing(graph: PlotGraph, palette: readonly string[]): PlotDrawing {
  const color = (index: number) => palette[index % palette.length];
  const drawn = graph.curves.map((curve, i) => ({
    id: String(i),
    expr: curve.label,
    visible: true,
    locked: true,
    color: color(curve.color),
    points: curve.segments.flat(),
    segments: curve.segments,
    invalid: false,
    cmp: "=" as const,
  }));
  const points: GraphPoints = { holes: [], marks: [] };
  for (const p of graph.points) {
    if (p.open) points.holes.push({ point: [p.x, p.y], color: color(p.color) });
    else points.marks.push({ point: [p.x, p.y], color: color(p.color), label: p.label });
  }
  const legend: PlotDrawing["legend"] = [
    ...graph.curves.filter((c) => c.label).map((c) => ({ label: c.label, color: c.color, role: "curve" as const })),
    ...graph.lines
      .filter((l) => l.label && l.role !== "segment")
      .map((l) => ({ label: l.label, color: l.color, role: l.role })),
  ];
  return { drawn, points, layers: { lines: graph.lines, regions: graph.regions }, legend };
}

