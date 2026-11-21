import { G, Ellipse, Line, Polygon, Polyline, Text as SvgText } from "react-native-svg";

import { arrowHead, rightAngleSquare, segmentLabelAt, tickStrokes, type Px } from "@/lib/math/planeMarks";
import { type PlaneRole, type PointsGraph } from "@/lib/math/pointsGraph";
import { type Theme } from "@/lib/theme";
import { Weight } from "@/lib/type";

const DASH = "5,4";
const FILL_OPACITY = 0.12;
const LABEL_FONT = 12;

/** The colour of each part: the question's shape, its image, a guide line. */
export function planeColor(theme: Theme, role: PlaneRole): string {
  if (role === "image") return theme.graphSeries[2];
  if (role === "guide") return theme.textSecondary;
  return theme.primary;
}

const toPoints = (points: Px[]) => points.map((p) => `${p.px},${p.py}`).join(" ");

/**
 * The segments, polygons, circles and right angles of a coordinate plane, in screen space:
 * fills under lines, lines under marks. `at` maps the server's coordinates to pixels.
 */
export function CoordinatePlaneShapes({
  graph,
  at,
  unitPx,
  middle,
  clipId,
  theme,
}: {
  graph: PointsGraph;
  at: (x: number, y: number) => Px;
  /** Pixels per unit on each axis, for a circle's radii. */
  unitPx: { x: number; y: number };
  /** The figure's middle in pixels: segment labels sit away from it. */
  middle: Px;
  clipId: string;
  theme: Theme;
}) {
  const pair = (p: [number, number]) => at(p[0], p[1]);
  return (
    <G>
      <G clipPath={`url(#${clipId})`}>
        {graph.polygons.map((polygon, i) => (
          <Polygon
            key={`fill-${i}`}
            points={toPoints(polygon.points.map(pair))}
            fill={planeColor(theme, polygon.role)}
            fillOpacity={FILL_OPACITY}
          />
        ))}
        {graph.circles.map((circle, i) => {
          const centre = pair(circle.center);
          return (
            <Ellipse
              key={`circle-${i}`}
              cx={centre.px}
              cy={centre.py}
              rx={circle.radius * unitPx.x}
              ry={circle.radius * unitPx.y}
              stroke={planeColor(theme, circle.role)}
              strokeWidth={2}
              strokeDasharray={circle.role === "image" ? DASH : undefined}
              fill="none"
            />
          );
        })}
        {graph.segments.map((segment, i) => {
          const start = pair(segment.start);
          const end = pair(segment.end);
          const color = planeColor(theme, segment.role);
          return (
            <G key={`seg-${i}`}>
              <Line
                x1={start.px}
                y1={start.py}
                x2={end.px}
                y2={end.py}
                stroke={color}
                strokeWidth={segment.role === "guide" ? 1.25 : 2}
                strokeDasharray={segment.dashed ? DASH : undefined}
              />
              {tickStrokes(start, end, segment.ticks).map(([a, b], t) => (
                <Line key={`tick-${t}`} x1={a.px} y1={a.py} x2={b.px} y2={b.py} stroke={color} strokeWidth={1.5} />
              ))}
              {segment.arrow ? <Polygon points={toPoints(arrowHead(start, end))} fill={color} /> : null}
            </G>
          );
        })}
        {graph.rightAngles.map((mark, i) => {
          const square = rightAngleSquare(pair(mark.at), pair(mark.a), pair(mark.b));
          return square.length ? (
            <Polyline key={`right-${i}`} points={toPoints(square)} stroke={theme.textSecondary} strokeWidth={1.25} fill="none" />
          ) : null;
        })}
      </G>
      {graph.segments.map((segment, i) => {
        if (!segment.label) return null;
        const spot = segmentLabelAt(pair(segment.start), pair(segment.end), middle);
        return (
          <SvgText
            key={`seg-label-${i}`}
            x={spot.px}
            y={spot.py}
            fill={segment.role === "guide" ? theme.textSecondary : theme.text}
            fontSize={LABEL_FONT}
            {...Weight.medium}
            textAnchor="middle"
          >
            {segment.label}
          </SvgText>
        );
      })}
    </G>
  );
}
