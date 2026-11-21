import { useId } from "react";
import { Text, View } from "react-native";
import Svg, { Circle, G, Text as SvgText } from "react-native-svg";

import { CartesianAxes } from "@/components/rich/CartesianAxes";
import { CoordinatePlaneShapes, planeColor } from "@/components/rich/CoordinatePlaneShapes";
import { GRAPH_AXIS_PAD } from "@/components/rich/GraphCanvas";
import { mapGraphPoint } from "@/lib/math/graphBlock";
import { pointLabelAt } from "@/lib/math/planeMarks";
import { pointsChartHeight, quadrantNumerals, type PointsGraph } from "@/lib/math/pointsGraph";
import { type Theme } from "@/lib/theme";
import { Weight } from "@/lib/type";

const DOT = 4;
const LABEL_FONT = 12;
/** A label's width estimate, for flipping it left near the right edge. */
const CHAR_EM = 0.6;

/** The middle of what the plane draws, in its own units: segment labels sit away from it. */
function figureMiddle(graph: PointsGraph): [number, number] {
  const spots: [number, number][] = [
    ...graph.points.map((p): [number, number] => [p.x, p.y]),
    ...graph.polygons.flatMap((polygon) => polygon.points),
  ];
  if (!spots.length) return [0, 0];
  const sum = spots.reduce((acc, [x, y]) => [acc[0] + x, acc[1] + y], [0, 0]);
  return [sum[0] / spots.length, sum[1] / spots.length];
}

/**
 * Lettered points on a coordinate plane, one unit as wide as it is tall where that fits,
 * with the segments, shapes, circles and a transformation's image the server drew there.
 */
export function CoordinatePlaneChart({
  graph,
  width,
  theme,
  styles,
}: {
  graph: PointsGraph;
  width: number;
  theme: Theme;
  styles: { wrap: object; title: object };
}) {
  const clipId = useId();
  const bounds = { xMin: graph.xMin, xMax: graph.xMax, yMin: graph.yMin, yMax: graph.yMax };
  const height = pointsChartHeight(graph, width, GRAPH_AXIS_PAD);
  const at = (x: number, y: number) => mapGraphPoint(x, y, bounds, width, height, GRAPH_AXIS_PAD);
  const unitPx = {
    x: (width - GRAPH_AXIS_PAD * 2) / (graph.xMax - graph.xMin),
    y: (height - GRAPH_AXIS_PAD * 2) / (graph.yMax - graph.yMin),
  };
  const [middleX, middleY] = figureMiddle(graph);
  const frame = { width, height, pad: GRAPH_AXIS_PAD };
  return (
    <View style={styles.wrap}>
      {graph.title ? <Text style={styles.title}>{graph.title}</Text> : null}
      <Svg
        width={width}
        height={height}
        testID="points-graph"
        accessibilityRole="image"
        accessibilityLabel={graph.points.map((point) => point.label).join(", ")}
      >
        <CartesianAxes
          width={width}
          height={height}
          pad={GRAPH_AXIS_PAD}
          bounds={bounds}
          clipId={clipId}
          axisColor={theme.textSecondary}
          labelColor={theme.textSecondary}
          gridColor={theme.border}
          xName="x"
          yName="y"
        />
        {graph.quadrants
          ? quadrantNumerals(graph).map((numeral) => {
              const { px, py } = at(numeral.x, numeral.y);
              return (
                <SvgText
                  key={numeral.text}
                  x={px}
                  y={py}
                  fill={theme.textSecondary}
                  fontSize={16}
                  {...Weight.semibold}
                  textAnchor="middle"
                  opacity={0.6}
                >
                  {numeral.text}
                </SvgText>
              );
            })
          : null}
        <CoordinatePlaneShapes
          graph={graph}
          at={at}
          unitPx={unitPx}
          middle={at(middleX, middleY)}
          clipId={clipId}
          theme={theme}
        />
        {graph.points.map((point, i) => {
          const spot = at(point.x, point.y);
          const label = pointLabelAt(spot, point.side, point.label.length * LABEL_FONT * CHAR_EM, frame);
          return (
            <G key={`${point.label}-${i}`}>
              <Circle cx={spot.px} cy={spot.py} r={DOT} fill={planeColor(theme, point.role)} />
              <SvgText
                x={label.x}
                y={label.y}
                fill={point.role === "image" ? planeColor(theme, "image") : theme.text}
                fontSize={LABEL_FONT}
                {...Weight.semibold}
                textAnchor={label.anchor}
              >
                {point.label}
              </SvgText>
            </G>
          );
        })}
      </Svg>
    </View>
  );
}
