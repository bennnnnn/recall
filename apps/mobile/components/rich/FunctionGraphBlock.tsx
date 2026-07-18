import { useMemo } from "react";
import { StyleSheet, Text, useWindowDimensions, View } from "react-native";
import { useTranslation } from "react-i18next";
import Svg, { Circle, Line, Polyline, Text as SvgText } from "react-native-svg";

import {
  graphBounds,
  graphPolylinePoints,
  mapGraphPoint,
  parseGraphSpec,
} from "@/lib/graphBlock";
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
  const { t } = useTranslation();
  const { width: screenWidth } = useWindowDimensions();
  const spec = useMemo(() => parseGraphSpec(content), [content]);
  const styles = useMemo(() => makeStyles(theme), [theme]);
  const chartWidth = Math.min(screenWidth - 48, 360);

  if (!spec) {
    return (
      <View style={styles.fallback}>
        <Text style={styles.fallbackText}>
          {t("rich.graph_error")}
        </Text>
      </View>
    );
  }

  const hasCurve2 = spec.type === "function" && !!spec.expr2 && !!spec.points2?.length;
  const title =
    spec.title ?? (spec.type === "vertical" ? spec.expr : `y = ${spec.expr}`);
  const bounds =
    spec.type === "vertical" && spec.x != null
      ? {
          xMin: (spec.x_min ?? spec.x - 5),
          xMax: (spec.x_max ?? spec.x + 5),
          yMin: spec.y_min ?? Math.min(...spec.points.map((p) => p[1])),
          yMax: spec.y_max ?? Math.max(...spec.points.map((p) => p[1])),
        }
      : graphBounds(spec.points, hasCurve2 ? spec.points2 : undefined);
  // A single point (or points sharing an x) has no line to draw — a
  // Polyline needs 2+ points to render anything visible. Vertical lines
  // intentionally share an x and still draw between the two endpoints.
  const polyline =
    spec.points.length >= 2
      ? graphPolylinePoints(spec.points, chartWidth, CHART_HEIGHT, bounds)
      : null;
  // When the backend detected a discontinuity (e.g. a tan(x) vertical
  // asymptote), render each segment as its own Polyline against the SAME
  // shared bounds — otherwise a naive single Polyline draws a near-vertical
  // line straight across the gap. Bounds must come from the full point set
  // (not per-segment) so all segments stay on one consistent axis scale.
  const segmentPolylines = spec.segments?.length
    ? spec.segments
        .filter((seg) => seg.length >= 2)
        .map((seg) =>
          graphPolylinePoints(seg, chartWidth, CHART_HEIGHT, bounds),
        )
    : null;
  const points2 = hasCurve2 ? spec.points2! : [];
  const polyline2 =
    hasCurve2 && points2.length >= 2
      ? graphPolylinePoints(points2, chartWidth, CHART_HEIGHT, bounds)
      : null;
  const segmentPolylines2 =
    hasCurve2 && spec.segments2?.length
      ? spec.segments2
          .filter((seg) => seg.length >= 2)
          .map((seg) => graphPolylinePoints(seg, chartWidth, CHART_HEIGHT, bounds))
      : null;
  const markers =
    spec.points.length <= MAX_MARKED_POINTS
      ? spec.points.map(([x, y]) =>
          mapGraphPoint(x, y, bounds, chartWidth, CHART_HEIGHT),
        )
      : [];
  const markers2 =
    hasCurve2 && points2.length <= MAX_MARKED_POINTS
      ? points2.map(([x, y]) => mapGraphPoint(x, y, bounds, chartWidth, CHART_HEIGHT))
      : [];
  const pad = 28;
  const axisColor = theme.border;
  const xAxisY = CHART_HEIGHT - pad;
  const yAxisX = pad;
  const curveColor2 = theme.accent;

  return (
    <View style={styles.wrap}>
      <Text style={styles.title}>{title}</Text>
      {hasCurve2 ? (
        <View style={styles.legendRow}>
          <View style={styles.legendItem}>
            <View style={[styles.legendDot, { backgroundColor: theme.primary }]} />
            <Text style={styles.legendText}>{spec.label ?? `y = ${spec.expr}`}</Text>
          </View>
          <View style={styles.legendItem}>
            <View style={[styles.legendDot, { backgroundColor: curveColor2 }]} />
            <Text style={styles.legendText}>{spec.label2 ?? `y = ${spec.expr2}`}</Text>
          </View>
        </View>
      ) : null}
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
        {segmentPolylines ? (
          segmentPolylines.map((pts, i) => (
            <Polyline
              key={i}
              points={pts}
              fill="none"
              stroke={theme.primary}
              strokeWidth={2.5}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          ))
        ) : polyline ? (
          <Polyline
            points={polyline}
            fill="none"
            stroke={theme.primary}
            strokeWidth={2.5}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        ) : null}
        {segmentPolylines2 ? (
          segmentPolylines2.map((pts, i) => (
            <Polyline
              key={`c2-${i}`}
              points={pts}
              fill="none"
              stroke={curveColor2}
              strokeWidth={2.5}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          ))
        ) : polyline2 ? (
          <Polyline
            points={polyline2}
            fill="none"
            stroke={curveColor2}
            strokeWidth={2.5}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        ) : null}
        {markers.map(({ px, py }, i) => (
          <Circle key={i} cx={px} cy={py} r={4} fill={theme.primary} />
        ))}
        {markers2.map(({ px, py }, i) => (
          <Circle key={`c2-${i}`} cx={px} cy={py} r={4} fill={curveColor2} />
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
        <SvgText
          x={yAxisX + 2}
          y={xAxisY + 16}
          fill={theme.textSecondary}
          fontSize={11}
        >
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
    legendRow: {
      flexDirection: "row",
      gap: 16,
      marginBottom: 8,
    },
    legendItem: {
      flexDirection: "row",
      alignItems: "center",
      gap: 6,
    },
    legendDot: {
      width: 8,
      height: 8,
      borderRadius: 4,
    },
    legendText: {
      fontFamily: CODE_FONT,
      fontSize: 12,
      color: theme.textSecondary,
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
