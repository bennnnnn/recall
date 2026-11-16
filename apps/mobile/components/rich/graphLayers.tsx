/**
 * What a server-drawn plot adds to a function graph (`lib/math/plotGraph.ts`): shaded
 * regions and rectangles under the curves, and stated lines, tangents, asymptotes and the
 * axis a region turns about over them. The SVG plot (`GraphCanvas`) draws them here; the
 * Skia plot in `skia/SkiaGraphLayers`.
 */
import { Line, Polygon, Text as SvgText } from "react-native-svg";

import { MIRROR_DASH, PLOT_DASH, PLOT_TURN, plotColor, plotStroke, REGION_OPACITY } from "@/components/rich/plotPaint";
import { mapGraphPoint } from "@/lib/math/graphBlock";
import { type GraphView } from "@/lib/math/graphViewport";
import { type GraphLayers } from "@/lib/math/plotGraph";
import { type Theme } from "@/lib/theme";

type Props = {
  layers: GraphLayers;
  /** "under" the curves (regions) or "over" them (lines). */
  part: "under" | "over";
  bounds: GraphView;
  width: number;
  height: number;
  pad: number;
  theme: Theme;
};

export function SvgGraphLayers({ layers, part, bounds, width, height, pad, theme }: Props) {
  const at = ([x, y]: [number, number]) => mapGraphPoint(x, y, bounds, width, height, pad);
  if (part === "under") {
    return (
      <>
        {layers.regions.map((region, i) => (
          <Polygon
            key={`region-${i}`}
            testID={`plot-region-${region.kind}`}
            points={region.points.map((p) => `${at(p).px},${at(p).py}`).join(" ")}
            fill={plotColor(theme, region.color)}
            fillOpacity={REGION_OPACITY[region.kind]}
            stroke={region.kind === "shade" ? "none" : plotColor(theme, region.color)}
            strokeWidth={1}
            strokeDasharray={region.kind === "mirror" ? MIRROR_DASH.join(" ") : undefined}
          />
        ))}
      </>
    );
  }
  return (
    <>
      {layers.lines.map((line, i) => {
        const stroke = plotStroke(theme, line.role, line.color);
        const [from, to] = [at(line.start), at(line.end)];
        return (
          <Line
            key={`line-${i}`}
            testID={`plot-line-${line.role}`}
            x1={from.px}
            y1={from.py}
            x2={to.px}
            y2={to.py}
            stroke={stroke.color}
            strokeWidth={stroke.width}
            strokeDasharray={PLOT_DASH[line.role]?.join(" ")}
            strokeLinecap="round"
          />
        );
      })}
      {layers.lines
        .filter((line) => line.role === "axis")
        .map((line, i) => {
          const end = at(line.end);
          return (
            <SvgText key={`turn-${i}`} x={Math.min(end.px, width - pad)} y={Math.max(end.py, pad + 10) - 6} fill={theme.text} fontSize={16} textAnchor="end">
              {PLOT_TURN}
            </SvgText>
          );
        })}
    </>
  );
}
