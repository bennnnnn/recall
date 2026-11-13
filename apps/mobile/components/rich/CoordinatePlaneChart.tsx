import { useId } from "react";
import { Text, View } from "react-native";
import Svg, { Circle, G, Text as SvgText } from "react-native-svg";

import { CartesianAxes } from "@/components/rich/CartesianAxes";
import { GRAPH_AXIS_PAD } from "@/components/rich/GraphCanvas";
import { mapGraphPoint } from "@/lib/math/graphBlock";
import { pointsChartHeight, quadrantNumerals, type PointsGraph } from "@/lib/math/pointsGraph";
import { type Theme } from "@/lib/theme";
import { Weight } from "@/lib/type";

const DOT = 4;
const LABEL_FONT = 12;
/** A label's width estimate, for flipping it left near the right edge. */
const CHAR_EM = 0.6;

/** Lettered points on a coordinate plane, one unit as wide as it is tall where that fits. */
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
        {graph.points.map((point) => {
          const { px, py } = at(point.x, point.y);
          const room = width - GRAPH_AXIS_PAD - px;
          const left = room < point.label.length * LABEL_FONT * CHAR_EM + 8;
          return (
            <G key={point.label}>
              <Circle cx={px} cy={py} r={DOT} fill={theme.primary} />
              <SvgText
                x={left ? px - 6 : px + 6}
                y={py - 6}
                fill={theme.text}
                fontSize={LABEL_FONT}
                {...Weight.semibold}
                textAnchor={left ? "end" : "start"}
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
