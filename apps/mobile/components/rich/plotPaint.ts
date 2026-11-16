/**
 * Paint a server-drawn plot's two renderers share (`PlotGraphCard`'s SVG and
 * `skia/SkiaPlotCanvas`), so the card looks the same in Expo Go and a native build.
 */
import { type PlotLineRole } from "@/lib/math/plotGraph";
import { type Theme } from "@/lib/theme";

export const PLOT_HEIGHT = 220;
/** Dash and gap: an asymptote is never mistaken for a curve, an axis of revolution for either. */
export const PLOT_DASH: Partial<Record<PlotLineRole, number[]>> = {
  asymptote: [6, 5],
  axis: [10, 4, 2, 4],
  segment: [4, 3],
};
export const REGION_OPACITY = { shade: 0.22, strip: 0.3, mirror: 0.08 } as const;
/** A slice turned about its axis is outlined dashed: where the solid is, not a region. */
export const MIRROR_DASH = [4, 3];
/** Drawn beside an axis of revolution: the turn the region makes about it. */
export const PLOT_TURN = "↻";

export function plotColor(theme: Theme, index: number): string {
  return theme.graphSeries[index % theme.graphSeries.length];
}

/** A line's stroke: an asymptote dashed and thin in its curve's colour (the server's
 * `color`), so a legend row names the lines of one curve only. */
export function plotStroke(theme: Theme, role: PlotLineRole, color: number): { color: string; width: number } {
  if (role === "asymptote") return { color: plotColor(theme, color), width: 1.5 };
  if (role === "axis") return { color: theme.text, width: 1.5 };
  return { color: plotColor(theme, color), width: 2 };
}
