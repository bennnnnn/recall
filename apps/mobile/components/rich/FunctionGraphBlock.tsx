import { useMemo } from "react";
import { StyleSheet, Text, useWindowDimensions, View } from "react-native";
import Svg, { Circle, Line, Polyline, Text as SvgText } from "react-native-svg";

import { graphBounds, graphPolylinePoints, mapGraphPoint, parseGraphSpec } from "@/lib/graphBlock";
import { CODE_FONT } from "@/lib/fonts";
import { Theme, useTheme } from "@/lib/theme";

type Props = { content: string };

const CHART_HEIGHT = 220;

// A handful of explicit points ("plot (2,3) and (5,1)") are individually
// meaningful and should each be visible as a marker; a dense function
// sample (up to 300 points) is a curve, not a set of markers to dot.
const MAX_MARKED_POINTS = 20;

function formatAxisNumber(n: number): string {
  return Number.isInteger(n) ? String(n) : n.toFixed(1);
}

export function FunctionGraphBlock({ content }: Props) {
  const theme = useTheme();
  const { width: screenWidth } = useWindowDimensions();
  const spec = useMemo(() => parseGraphSpec(content), [content]);
  const styles = useMemo(() => makeStyles(theme), [theme]);
  const chartWidth = Math.min(screenWidth - 48, 360);

  if (!spec) {
    return (
      <View style={styles.fallback}>
        <Text style={styles.fallbackText}>Could not render function graph.</Text>
      </View>
    );
  }

  const bounds = graphBounds(spec.points);
  // A single point (or points sharing an x) has no line to draw — a
  // Polyline needs 2+ points to render anything visible.
  const polyline = spec.points.length >= 2 ? graphPolylinePoints(spec.points, chartWidth, CHART_HEIGHT) : null;
  const markers =
    spec.points.length <= MAX_MARKED_POINTS
      ? spec.points.map(([x, y]) => mapGraphPoint(x, y, bounds, chartWidth, CHART_HEIGHT))
      : [];
  const pad = 28;
  const axisColor = theme.border;
  const xAxisY = CHART_HEIGHT - pad;
  const yAxisX = pad;

  return (
    <View style={styles.wrap}>
      <Text style={styles.title}>{spec.title ?? `y = ${spec.expr}`}</Text>
      <Svg width={chartWidth} height={CHART_HEIGHT}>
        <Line
          x1={yAxisX}
          y1={pad}
          x2={yAxisX}
          y2={xAxisY}
          stroke={axisColor}
          strokeWidth={1}
        />
        <Line
          x1={yAxisX}
          y1={xAxisY}
          x2={chartWidth - pad}
          y2={xAxisY}
          stroke={axisColor}
          strokeWidth={1}
        />
        {polyline ? (
          <Polyline
            points={polyline}
            fill="none"
            stroke={theme.primary}
            strokeWidth={2.5}
          />
        ) : null}
        {markers.map(({ px, py }, i) => (
          <Circle key={i} cx={px} cy={py} r={4} fill={theme.primary} />
        ))}
        <SvgText
          x={chartWidth - pad}
          y={xAxisY - 6}
          fill={theme.textSecondary}
          fontSize={11}
          textAnchor="end"
        >
          {spec.variable}
        </SvgText>
        {/* Number line: min/max value at both ends of each axis. */}
        <SvgText x={4} y={pad + 4} fill={theme.textSecondary} fontSize={11}>
          {formatAxisNumber(bounds.yMax)}
        </SvgText>
        <SvgText x={4} y={xAxisY - 2} fill={theme.textSecondary} fontSize={11}>
          {formatAxisNumber(bounds.yMin)}
        </SvgText>
        <SvgText x={yAxisX + 2} y={xAxisY + 16} fill={theme.textSecondary} fontSize={11}>
          {formatAxisNumber(bounds.xMin)}
        </SvgText>
        <SvgText
          x={chartWidth - pad}
          y={xAxisY + 16}
          fill={theme.textSecondary}
          fontSize={11}
          textAnchor="end"
        >
          {formatAxisNumber(bounds.xMax)}
        </SvgText>
      </Svg>
    </View>
  );
}

const makeStyles = (theme: Theme) =>
  StyleSheet.create({
    wrap: {
      marginVertical: 8,
      alignItems: "center",
    },
    title: {
      fontFamily: CODE_FONT,
      fontSize: 14,
      color: theme.text,
      marginBottom: 6,
      textAlign: "center",
    },
    fallback: {
      marginVertical: 8,
      padding: 12,
      borderRadius: 10,
      backgroundColor: theme.contentSurface,
    },
    fallbackText: {
      color: theme.textSecondary,
      fontSize: 14,
    },
  });
