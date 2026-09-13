import Svg, { Circle, G, Polyline } from "react-native-svg";

import { CartesianAxes } from "@/components/rich/CartesianAxes";
import { type DrawnSeries } from "@/hooks/useInteractiveGraph";
import {
  graphPolylinePoints,
  graphXIntercepts,
  interiorVertex,
  mapGraphPoint,
  SHIFTED_VERTEX_MIN,
  type GraphSpec,
} from "@/lib/graphBlock";
import { type GraphView } from "@/lib/graphViewport";
import { Theme } from "@/lib/theme";

export const GRAPH_AXIS_PAD = 28;
const MAX_MARKED_POINTS = 20;

type Props = {
  spec: GraphSpec;
  theme: Theme;
  clipId: string;
  width: number;
  height: number;
  bounds: GraphView;
  drawn: DrawnSeries[];
  verticalX?: number;
};

export function GraphCanvas({
  spec,
  theme,
  clipId,
  width,
  height,
  bounds,
  drawn,
  verticalX,
}: Props) {
  const isVerticalLine = verticalX != null;
  const visibleSeries = drawn.filter((row) => row.visible);
  const primary = drawn[0];
  const inView = ([x, y]: [number, number]) =>
    x >= bounds.xMin && x <= bounds.xMax && y >= bounds.yMin && y <= bounds.yMax;
  const scatterMarkers =
    !isVerticalLine &&
    visibleSeries.length === 1 &&
    primary.points.length <= MAX_MARKED_POINTS
      ? primary.points.filter(inView).map(([x, y]) => mapGraphPoint(x, y, bounds, width, height))
      : [];
  const vertex =
    !isVerticalLine && visibleSeries.length === 1 ? interiorVertex(primary.points) : null;
  const rootMarkers =
    vertex && Math.abs(vertex.y) >= SHIFTED_VERTEX_MIN
      ? graphXIntercepts(primary.points)
          .filter((x) => x >= bounds.xMin && x <= bounds.xMax)
          .slice(0, 3)
          .map((x) => mapGraphPoint(x, 0, bounds, width, height))
      : [];
  const clip = `url(#${clipId})`;

  return (
    <Svg width={width} height={height}>
      <CartesianAxes
        width={width}
        height={height}
        pad={GRAPH_AXIS_PAD}
        bounds={bounds}
        clipId={clipId}
        axisColor={theme.textSecondary}
        labelColor={theme.textSecondary}
        gridColor={theme.border}
        xName={spec.variable ?? "x"}
        yName="y"
        fractionalTicks
      />
      <G clipPath={clip}>
        {isVerticalLine ? (
          <Polyline
            points={graphPolylinePoints(
              [
                [verticalX, bounds.yMin],
                [verticalX, bounds.yMax],
              ],
              width,
              height,
              bounds,
            )}
            fill="none"
            stroke={theme.primary}
            strokeWidth={2.5}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        ) : (
          visibleSeries.map((row) => (
            <SeriesPolylines key={row.id} row={row} width={width} height={height} bounds={bounds} />
          ))
        )}
      </G>
      {scatterMarkers.map(({ px, py }, i) => (
        <Circle key={i} cx={px} cy={py} r={4} fill={primary.color} />
      ))}
      {rootMarkers.map(({ px, py }, i) => (
        <Circle key={`root-${i}`} cx={px} cy={py} r={4} fill={theme.danger} />
      ))}
    </Svg>
  );
}

function SeriesPolylines({
  row,
  width,
  height,
  bounds,
}: {
  row: DrawnSeries;
  width: number;
  height: number;
  bounds: GraphView;
}) {
  const segs = row.segments?.filter((seg) => seg.length >= 2);
  if (segs && segs.length > 1) {
    return (
      <>
        {segs.map((seg, i) => (
          <Polyline
            key={`${row.id}-${i}`}
            points={graphPolylinePoints(seg, width, height, bounds)}
            fill="none"
            stroke={row.color}
            strokeWidth={2.5}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        ))}
      </>
    );
  }
  if (row.points.length < 2) return null;
  return (
    <Polyline
      points={graphPolylinePoints(row.points, width, height, bounds)}
      fill="none"
      stroke={row.color}
      strokeWidth={2.5}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  );
}
