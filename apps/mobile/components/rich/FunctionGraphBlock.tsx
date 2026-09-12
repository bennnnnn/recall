import { useId, useMemo } from "react";
import { StyleSheet, Text, useWindowDimensions, View } from "react-native";
import { useTranslation } from "react-i18next";
import Svg, { Circle, G, Polyline } from "react-native-svg";

import { CartesianAxes } from "@/components/rich/CartesianAxes";
import { NumberLineChart } from "@/components/rich/NumberLineChart";
import { InequalityGraphChart } from "@/components/rich/InequalityGraphChart";
import {
  expandBoundsForAxes,
  formatGraphExpr,
  formatInequalityExpr,
  graphBounds,
  graphPolylinePoints,
  mapGraphPoint,
  parseGraphSpec,
  schoolViewBounds,
  type GraphSpec,
} from "@/lib/graphBlock";
import { CODE_FONT } from "@/lib/fonts";
import { Theme, useTheme } from "@/lib/theme";

type Props = { content: string };

const CHART_HEIGHT = 220;
const NUMBER_LINE_HEIGHT = 80;

// A handful of explicit points ("plot (2,3) and (5,1)") are individually
// meaningful and should each be visible as a marker; a dense function
// sample (up to 300 points) is a curve, not a set of markers to dot.
const MAX_MARKED_POINTS = 20;

export function FunctionGraphBlock({ content }: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const { width: screenWidth } = useWindowDimensions();
  const spec = useMemo(() => parseGraphSpec(content), [content]);
  const styles = useMemo(() => makeStyles(theme), [theme]);
  const chartWidth = Math.min(screenWidth - 48, 360);
  const clipId = useId().replace(/:/g, "");

  if (!spec) {
    return (
      <View style={styles.fallback}>
        <Text style={styles.fallbackText}>
          {t("rich.graph_error")}
        </Text>
      </View>
    );
  }

  if (spec.type === "number_line") {
    return (
      <View style={styles.wrap}>
        <Text style={styles.title}>
          {formatInequalityExpr(formatGraphExpr(spec.title ?? spec.expr))}
        </Text>
        <NumberLineChart
          spec={spec}
          width={chartWidth}
          height={NUMBER_LINE_HEIGHT}
          color={theme.primary}
          axisColor={theme.border}
          labelColor={theme.textSecondary}
          surfaceColor={theme.bg}
        />
      </View>
    );
  }

  if (spec.type === "inequality") {
    return <InequalityGraphChart spec={spec} width={chartWidth} />;
  }

  if (spec.type === "trajectory") {
    return (
      <TrajectoryChart
        spec={spec}
        chartWidth={chartWidth}
        styles={styles}
        theme={theme}
      />
    );
  }

  const hasCurve2 = spec.type === "function" && !!spec.expr2 && !!spec.points2?.length;
  const verticalX = spec.type === "vertical" ? spec.x : undefined;
  const isVerticalLine = verticalX != null;
  const title = formatGraphExpr(
    spec.title ??
      (spec.type === "vertical" ? spec.expr : `y = ${formatGraphExpr(spec.expr)}`),
  );
  const pad = 28;
  const innerW = chartWidth - pad * 2;
  const innerH = CHART_HEIGHT - pad * 2;
  const plotAspect = innerW / innerH;
  const bounds = isVerticalLine
    ? expandBoundsForAxes(
        {
          xMin: spec.x_min ?? 0,
          xMax: spec.x_max ?? Math.max(Math.abs(2 * verticalX), 10),
          yMin: spec.y_min ?? Math.min(...spec.points.map((p) => p[1])),
          yMax: spec.y_max ?? Math.max(...spec.points.map((p) => p[1])),
        },
        { pad: false },
      )
    : schoolViewBounds(
        graphBounds(spec.points, hasCurve2 ? spec.points2 : undefined),
        plotAspect,
      );
  // A single point (or points sharing an x) has no line to draw — a
  // Polyline needs 2+ points to render anything visible. Vertical lines
  // run the full axis height so they read as x = c, not a capped segment.
  const linePoints: [number, number][] = isVerticalLine
    ? [
        [verticalX, bounds.yMin],
        [verticalX, bounds.yMax],
      ]
    : spec.points;
  const polyline =
    linePoints.length >= 2
      ? graphPolylinePoints(linePoints, chartWidth, CHART_HEIGHT, bounds)
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
  const inView = ([x, y]: [number, number]) =>
    x >= bounds.xMin && x <= bounds.xMax && y >= bounds.yMin && y <= bounds.yMax;
  const markers =
    isVerticalLine || spec.points.length > MAX_MARKED_POINTS
      ? []
      : spec.points.filter(inView).map(([x, y]) =>
          mapGraphPoint(x, y, bounds, chartWidth, CHART_HEIGHT),
        );
  const markers2 =
    hasCurve2 && points2.length <= MAX_MARKED_POINTS
      ? points2.filter(inView).map(([x, y]) =>
          mapGraphPoint(x, y, bounds, chartWidth, CHART_HEIGHT),
        )
      : [];
  const origin = mapGraphPoint(0, 0, bounds, chartWidth, CHART_HEIGHT);
  const showVertex =
    !isVerticalLine &&
    bounds.xMin <= 0 &&
    bounds.xMax >= 0 &&
    bounds.yMin <= 0 &&
    bounds.yMax >= 0 &&
    spec.points.some(([x, y]) => Math.abs(x) < 0.35 && Math.abs(y) < 0.35);
  const curveColor2 = theme.accent;
  const clip = `url(#${clipId})`;

  return (
    <View style={styles.wrap}>
      <Text style={styles.title}>{title}</Text>
      {hasCurve2 ? (
        <View style={styles.legendRow}>
          <View style={styles.legendItem}>
            <View style={[styles.legendDot, { backgroundColor: theme.primary }]} />
            <Text style={styles.legendText}>
              {formatGraphExpr(spec.label ?? `y = ${formatGraphExpr(spec.expr)}`)}
            </Text>
          </View>
          <View style={styles.legendItem}>
            <View style={[styles.legendDot, { backgroundColor: curveColor2 }]} />
            <Text style={styles.legendText}>
              {formatGraphExpr(spec.label2 ?? `y = ${formatGraphExpr(spec.expr2 ?? "")}`)}
            </Text>
          </View>
        </View>
      ) : null}
      <Svg width={chartWidth} height={CHART_HEIGHT}>
        <CartesianAxes
          width={chartWidth}
          height={CHART_HEIGHT}
          pad={pad}
          bounds={bounds}
          clipId={clipId}
          axisColor={theme.textSecondary}
          labelColor={theme.textSecondary}
          gridColor={theme.border}
          xName={spec.variable ?? "x"}
          yName="y"
        />
        <G clipPath={clip}>
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
        </G>
        {markers.map(({ px, py }, i) => (
          <Circle key={i} cx={px} cy={py} r={4} fill={theme.primary} />
        ))}
        {markers2.map(({ px, py }, i) => (
          <Circle key={`c2-${i}`} cx={px} cy={py} r={4} fill={curveColor2} />
        ))}
        {showVertex ? (
          <Circle
            cx={origin.px}
            cy={origin.py}
            r={5}
            fill={theme.surface}
            stroke={theme.primary}
            strokeWidth={2}
          />
        ) : null}
      </Svg>
    </View>
  );
}

type TrajectoryChartProps = {
  spec: GraphSpec;
  chartWidth: number;
  styles: ReturnType<typeof makeStyles>;
  theme: Theme;
};

function TrajectoryChart({ spec, chartWidth, styles, theme }: TrajectoryChartProps) {
  const pad = 28;
  const clipId = useId().replace(/:/g, "");
  const bounds = expandBoundsForAxes(graphBounds(spec.points), { pad: false });
  const polyline = graphPolylinePoints(spec.points, chartWidth, CHART_HEIGHT, bounds);
  const xLabel = spec.x_label ?? "x";
  const yLabel = spec.y_label ?? "y";
  const title = formatGraphExpr(spec.title ?? "Trajectory");

  return (
    <View style={styles.wrap}>
      <Text style={styles.title}>{title}</Text>
      <Svg width={chartWidth} height={CHART_HEIGHT}>
        <CartesianAxes
          width={chartWidth}
          height={CHART_HEIGHT}
          pad={pad}
          bounds={bounds}
          clipId={clipId}
          axisColor={theme.textSecondary}
          labelColor={theme.textSecondary}
          gridColor={theme.border}
          xName={xLabel}
          yName={yLabel}
        />
        <G clipPath={`url(#${clipId})`}>
          <Polyline
            points={polyline}
            fill="none"
            stroke={theme.primary}
            strokeWidth={2.5}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </G>
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
      fontSize: 15,
      fontWeight: "600",
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
