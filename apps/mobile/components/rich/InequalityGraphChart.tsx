import { useId, useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import Svg, { Circle, G, Line, Polygon, Polyline } from "react-native-svg";

import { CartesianAxes } from "@/components/rich/CartesianAxes";
import { formatGraphExpr, formatInequalityExpr, graphPolylinePoints, mapGraphPoint, type InequalityGraphSpec } from "@/lib/graphBlock";
import { clipInequalityRegion } from "@/lib/inequalityGraph";
import { useTheme } from "@/lib/theme";

const CHART_HEIGHT = 220;
const PAD = 28;
const REGION_OPACITY = 0.16;
const STRICT_DASH = [6, 5];

/** Native SVG for a verified half-plane; no expression evaluation on-device. */
export function InequalityGraphChart({ spec, width }: { spec: InequalityGraphSpec; width: number }) {
  const theme = useTheme();
  const { t } = useTranslation();
  const clipId = useId().replace(/:/g, "");
  const geometry = useMemo(() => clipInequalityRegion(spec), [spec]);
  const bounds = { xMin: spec.x_min, xMax: spec.x_max, yMin: spec.y_min, yMax: spec.y_max };
  const title = formatInequalityExpr(formatGraphExpr(spec.title ?? spec.expr));
  const formula = formatInequalityExpr(formatGraphExpr(spec.expr));
  const strict = spec.comparator === "<" || spec.comparator === ">";
  const regionLabel = t("rich.graph_solution_region");
  const boundaryLabel = t(strict ? "rich.graph_boundary_excluded" : "rich.graph_boundary_included");
  const mapped = (points: [number, number][]) => graphPolylinePoints(points, width, CHART_HEIGHT, bounds);

  if (!geometry) {
    return <Text style={{ color: theme.textSecondary }}>{t("rich.graph_error")}</Text>;
  }
  const includedCorner = !strict && geometry.boundary.length === 1
    ? mapGraphPoint(geometry.boundary[0][0], geometry.boundary[0][1], bounds, width, CHART_HEIGHT)
    : null;

  return (
    <View style={styles.wrap}>
      <Text style={[styles.title, { color: theme.text }]}>{title}</Text>
      <Svg
        width={width}
        height={CHART_HEIGHT}
        accessible
        accessibilityRole="image"
        accessibilityLabel={`${formula}. ${regionLabel}. ${boundaryLabel}.`}
        testID="inequality-graph"
      >
        {/* The polygon is already clipped to the viewport. Draw it before
            axes so grid/tick contrast is not reduced by the fill. */}
        {geometry.region.length >= 3 ? (
          <Polygon testID="inequality-region" points={mapped(geometry.region)} fill={theme.primary} fillOpacity={REGION_OPACITY} />
        ) : null}
        <CartesianAxes
          width={width} height={CHART_HEIGHT} pad={PAD} bounds={bounds} clipId={clipId}
          axisColor={theme.textSecondary} labelColor={theme.textSecondary} gridColor={theme.border}
          xName="x" yName="y" keepAxesInView fractionalTicks
        />
        <G clipPath={`url(#${clipId})`}>
          {geometry.boundary.length >= 2 ? (
            <Polyline
              testID="inequality-boundary"
              points={mapped(geometry.boundary)} fill="none" stroke={theme.primary}
              strokeWidth={2.5} strokeDasharray={strict ? STRICT_DASH : undefined}
              strokeLinecap="butt"
            />
          ) : null}
        </G>
        {includedCorner ? (
          <Circle testID="inequality-boundary-point" cx={includedCorner.px} cy={includedCorner.py} r={3.5} fill={theme.primary} />
        ) : null}
      </Svg>
      <View style={styles.legend}>
        <View style={styles.legendItem}>
          <View style={[styles.swatch, { backgroundColor: theme.primary, opacity: REGION_OPACITY }]} />
          <Text style={[styles.legendText, { color: theme.textSecondary }]}>{regionLabel}</Text>
        </View>
        <View style={styles.legendItem}>
          <Svg width={24} height={8}>
            <Line x1={0} y1={4} x2={24} y2={4} stroke={theme.primary} strokeWidth={2.5} strokeDasharray={strict ? STRICT_DASH : undefined} />
          </Svg>
          <Text style={[styles.legendText, { color: theme.textSecondary }]}>{boundaryLabel}</Text>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { marginVertical: 8, alignItems: "center", maxWidth: "100%" },
  title: { fontSize: 15, fontWeight: "600", marginBottom: 6, textAlign: "center" },
  legend: { gap: 6, alignSelf: "stretch", paddingHorizontal: PAD },
  legendItem: { flexDirection: "row", alignItems: "center", gap: 8 },
  legendText: { fontSize: 12, lineHeight: 17, flexShrink: 1 },
  swatch: { width: 24, height: 12, borderRadius: 2 },
});
