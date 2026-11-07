/**
 * The points a function plot draws over its curves: open holes, and the labelled points
 * the fence lists (`GraphSpec.marks`: roots, turning points, intercepts, meetings, from
 * SymPy). The card's SVG plot draws them here; the Skia plot in `skia/SkiaGraphPoints`.
 */
import { Circle, G, Text as SvgText } from "react-native-svg";

import { GRAPH_TICK_FONT_SIZE } from "@/components/rich/graphPaint";
import { mapGraphPoint } from "@/lib/math/graphBlock";
import { formatShortW, markLabelW } from "@/lib/math/graphWorklets";
import { type GraphView } from "@/lib/math/graphViewport";
import { type Theme } from "@/lib/theme";
import { Weight } from "@/lib/type";

export type GraphHoleMarker = {
  point: [number, number];
  color: string;
};

/** A marked point on a curve still drawn as the server sent it. */
export type GraphMarkMarker = GraphHoleMarker & { label: string };

export type GraphPoints = { holes: GraphHoleMarker[]; marks: GraphMarkMarker[] };

export const NO_GRAPH_POINTS: GraphPoints = { holes: [], marks: [] };

/** A mark's dot, a touch smaller than a hole's ring. */
export const MARK_RADIUS = 4;
/** An estimate of the label face's advance, for keeping the label inside the plot. */
const MARK_CHAR_EM = 0.55;

/** "(2, −1)": the server's label, or the coordinates when it gave none. */
export function markLabel(x: number, y: number, label?: string): string {
  const coordinate = (n: number) => formatShortW(n).replace("-", "−");
  return label ?? `(${coordinate(x)}, ${coordinate(y)})`;
}

export function markLabelWidth(label: string): number {
  return label.length * GRAPH_TICK_FONT_SIZE * MARK_CHAR_EM;
}

function inView([x, y]: [number, number], bounds: GraphView): boolean {
  return x >= bounds.xMin && x <= bounds.xMax && y >= bounds.yMin && y <= bounds.yMax;
}

/** Holes and marks in the SVG plot, each where it is in view. */
export function SvgGraphPoints({
  points,
  bounds,
  width,
  height,
  pad,
  theme,
}: {
  points: GraphPoints;
  bounds: GraphView;
  width: number;
  height: number;
  pad: number;
  theme: Theme;
}) {
  const at = ([x, y]: [number, number]) => mapGraphPoint(x, y, bounds, width, height, pad);
  return (
    <>
      {points.holes.filter(({ point }) => inView(point, bounds)).map(({ point, color }, i) => {
        const { px, py } = at(point);
        return (
          <Circle
            key={`hole-${i}`}
            testID={`graph-hole-${i}`}
            cx={px}
            cy={py}
            r={5}
            fill={theme.elevated}
            stroke={color}
            strokeWidth={2.25}
          />
        );
      })}
      {points.marks.filter(({ point }) => inView(point, bounds)).map(({ point, color, label }, i) => {
        const { px, py } = at(point);
        const spot = markLabelW(px, py, markLabelWidth(label), GRAPH_TICK_FONT_SIZE, width, height, pad);
        const text = { x: spot.x, y: spot.y, fontSize: GRAPH_TICK_FONT_SIZE, ...Weight.semibold };
        return (
          <G key={`mark-${i}`} testID={`graph-mark-${i}`}>
            <Circle cx={px} cy={py} r={MARK_RADIUS} fill={color} stroke={theme.surface} strokeWidth={1.5} />
            {/* A halo in the plot's surface, so a grid line or the curve never strikes it through. */}
            <SvgText {...text} fill={theme.surface} stroke={theme.surface} strokeWidth={3}>
              {label}
            </SvgText>
            <SvgText {...text} fill={theme.text} testID={`graph-mark-label-${i}`}>
              {label}
            </SvgText>
          </G>
        );
      })}
    </>
  );
}
