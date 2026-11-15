import { Suspense, lazy, useId, useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";
import Svg, { Circle, G, Line, Polygon, Polyline, Text as SvgText } from "react-native-svg";

import { CartesianAxes } from "@/components/rich/CartesianAxes";
import { GRAPH_AXIS_PAD } from "@/components/rich/GraphCanvas";
import { GRAPH_TICK_FONT_SIZE } from "@/components/rich/graphPaint";
import {
  MIRROR_DASH,
  PLOT_DASH,
  PLOT_HEIGHT,
  PLOT_TURN,
  plotColor,
  plotStroke,
  REGION_OPACITY,
} from "@/components/rich/plotPaint";
import { isSkiaAvailable } from "@/lib/skiaAvailability";
import { plotDescription, plotLayout, type PlotGraph, type PlotLayout } from "@/lib/math/plotGraph";
import { Space } from "@/lib/space";
import { type Theme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";

const SkiaPlotCanvas = lazy(() =>
  import("@/components/rich/skia/SkiaPlotCanvas").then((m) => ({ default: m.SkiaPlotCanvas })),
);

const points = (path: { px: number; py: number }[]) => path.map(({ px, py }) => `${px},${py}`).join(" ");

/** The plot drawn in SVG: the fallback where Skia is not linked (Expo Go), and in tests. */
export function SvgPlotCanvas({
  graph,
  layout,
  width,
  theme,
}: {
  graph: PlotGraph;
  layout: PlotLayout;
  width: number;
  theme: Theme;
}) {
  const clipId = useId();
  const clip = `url(#${clipId})`;
  return (
    <Svg width={width} height={PLOT_HEIGHT} testID="plot-graph-svg">
      <CartesianAxes
        width={width}
        height={PLOT_HEIGHT}
        pad={GRAPH_AXIS_PAD}
        bounds={layout.bounds}
        clipId={clipId}
        axisColor={theme.textSecondary}
        labelColor={theme.textSecondary}
        gridColor={theme.border}
        xName={graph.xLabel}
        yName={graph.yLabel}
        keepAxesInView
        fractionalTicks
      />
      <G clipPath={clip}>
        {layout.regions.map((region, i) => (
          <Polygon
            key={`region-${i}`}
            testID={`plot-region-${region.kind}`}
            points={points(region.points)}
            fill={plotColor(theme, region.color)}
            fillOpacity={REGION_OPACITY[region.kind]}
            stroke={region.kind === "shade" ? "none" : plotColor(theme, region.color)}
            strokeWidth={1}
            strokeDasharray={region.kind === "mirror" ? MIRROR_DASH.join(" ") : undefined}
          />
        ))}
        {layout.curves.flatMap((curve, i) =>
          curve.paths.map((path, j) => (
            <Polyline
              key={`curve-${i}-${j}`}
              testID="plot-curve"
              points={points(path)}
              fill="none"
              stroke={plotColor(theme, curve.color)}
              strokeWidth={2.5}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )),
        )}
        {layout.lines.map((line, i) => {
          const stroke = plotStroke(theme, line.role, line.color);
          return (
            <Line
              key={`line-${i}`}
              testID={`plot-line-${line.role}`}
              x1={line.from.px}
              y1={line.from.py}
              x2={line.to.px}
              y2={line.to.py}
              stroke={stroke.color}
              strokeWidth={stroke.width}
              strokeDasharray={PLOT_DASH[line.role]?.join(" ")}
              strokeLinecap="round"
            />
          );
        })}
      </G>
      {layout.turns.map((turn, i) => (
        <SvgText key={`turn-${i}`} x={turn.px} y={turn.py - 6} fill={theme.text} fontSize={16} textAnchor="end">
          {PLOT_TURN}
        </SvgText>
      ))}
      {layout.dots.map((dot, i) => (
        <Circle
          key={`dot-${i}`}
          testID={dot.open ? "plot-dot-open" : "plot-dot"}
          cx={dot.at.px}
          cy={dot.at.py}
          r={dot.open ? 4.5 : 4}
          fill={dot.open ? theme.elevated : plotColor(theme, dot.color)}
          stroke={dot.open ? plotColor(theme, dot.color) : theme.surface}
          strokeWidth={dot.open ? 2 : 1.5}
        />
      ))}
      {layout.labels.map((label, i) => {
        const at = { x: label.x, y: label.y, fontSize: GRAPH_TICK_FONT_SIZE, textAnchor: label.anchor, ...Weight.semibold };
        return (
          <G key={`label-${i}`}>
            <SvgText {...at} fill={theme.surface} stroke={theme.surface} strokeWidth={3}>
              {label.text}
            </SvgText>
            <SvgText {...at} fill={theme.text} testID="plot-label">
              {label.text}
            </SvgText>
          </G>
        );
      })}
    </Svg>
  );
}

function Legend({ layout, theme }: { layout: PlotLayout; theme: Theme }) {
  if (!layout.legend.length) return null;
  return (
    <View style={styles.legend} testID="plot-legend">
      {layout.legend.map((row, i) => {
        const stroke = row.role === "curve" ? { color: plotColor(theme, row.color), width: 2.5 } : plotStroke(theme, row.role, row.color);
        const dashed = row.role !== "curve" && PLOT_DASH[row.role] != null;
        return (
          <View key={`legend-${i}`} style={styles.row}>
            <View
              style={[
                styles.swatch,
                { borderColor: stroke.color, borderTopWidth: stroke.width, borderStyle: dashed ? "dashed" : "solid" },
              ]}
            />
            <Text style={[styles.text, { color: theme.text }]}>{row.label}</Text>
          </View>
        );
      })}
    </View>
  );
}

/** A server-drawn plot: its canvas (Skia where linked, else SVG) and its legend. */
export function PlotGraphCard({ graph, width, theme }: { graph: PlotGraph; width: number; theme: Theme }) {
  const layout = useMemo(() => plotLayout(graph, width, PLOT_HEIGHT, GRAPH_AXIS_PAD), [graph, width]);
  const svg = <SvgPlotCanvas graph={graph} layout={layout} width={width} theme={theme} />;
  return (
    <View style={[styles.card, { width }]} testID="plot-graph">
      <View accessible accessibilityRole="image" accessibilityLabel={plotDescription(graph)}>
        {isSkiaAvailable() ? (
          <Suspense fallback={svg}>
            <SkiaPlotCanvas graph={graph} layout={layout} width={width} theme={theme} />
          </Suspense>
        ) : (
          svg
        )}
      </View>
      <Legend layout={layout} theme={theme} />
    </View>
  );
}

const styles = StyleSheet.create({
  card: { marginVertical: Space.xs, alignSelf: "center" },
  legend: { marginTop: Space.xxs, paddingHorizontal: GRAPH_AXIS_PAD, gap: 2 },
  row: { flexDirection: "row", alignItems: "center", gap: Space.xs },
  swatch: { width: 18, height: 0 },
  text: { ...Type.secondary },
});
