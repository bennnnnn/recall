import { Suspense, useCallback, useId, useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";

import { GraphCanvas, GRAPH_AXIS_PAD } from "@/components/rich/GraphCanvas";
import { PLOT_DASH, PLOT_HEIGHT, plotColor, plotStroke } from "@/components/rich/plotPaint";
import { SkiaGraphCanvasLazy, SkiaGraphLayersLazy } from "@/components/rich/skia/SkiaGraphCanvasLazy";
import { useSkiaGraphViewport } from "@/hooks/useSkiaGraphViewport";
import { type GraphView } from "@/lib/math/graphViewport";
import { plotDrawing, type PlotDrawing } from "@/components/rich/plotDrawing";
import { plotAxes, plotBounds, plotDescription, type PlotGraph } from "@/lib/math/plotGraph";
import { isSkiaAvailable } from "@/lib/skiaAvailability";
import { Space } from "@/lib/space";
import { type Theme } from "@/lib/theme";
import { Type } from "@/lib/type";

type Canvas = {
  graph: PlotGraph;
  drawing: PlotDrawing;
  bounds: GraphView;
  width: number;
  theme: Theme;
};

/** The Skia function graph, held still on the server's window: a plot has no pan or zoom. */
function SkiaPlot({ graph, drawing, bounds, width, theme }: Canvas) {
  const still = useCallback(() => {}, []);
  const viewport = useSkiaGraphViewport({
    width,
    height: PLOT_HEIGHT,
    pad: GRAPH_AXIS_PAD,
    initialView: bounds,
    onCommit: still,
  });
  const frame = { bounds: viewport.bounds, width, height: PLOT_HEIGHT, pad: GRAPH_AXIS_PAD };
  return (
    <View style={{ width, height: PLOT_HEIGHT }}>
      <SkiaGraphCanvasLazy
        drawn={drawing.drawn}
        points={drawing.points}
        xName={graph.xLabel}
        yName={graph.yLabel}
        width={width}
        height={PLOT_HEIGHT}
        pad={GRAPH_AXIS_PAD}
        theme={theme}
        viewport={viewport}
        testID="plot-graph-skia"
      />
      <SkiaGraphLayersLazy layers={drawing.layers} frame={frame} theme={theme} />
    </View>
  );
}

function Legend({ drawing, theme }: { drawing: PlotDrawing; theme: Theme }) {
  if (!drawing.legend.length) return null;
  return (
    <View style={styles.legend} testID="plot-legend">
      {drawing.legend.map((row, i) => {
        const stroke =
          row.role === "curve"
            ? { color: plotColor(theme, row.color), width: 2.5 }
            : plotStroke(theme, row.role, row.color);
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

/**
 * A server-drawn plot: the function graph's own canvas (Skia where linked, else SVG) on the
 * server's window, its layers and points the server's, and a legend of its equations.
 */
export function PlotGraphCard({ graph, width, theme }: { graph: PlotGraph; width: number; theme: Theme }) {
  const clipId = useId();
  const bounds = useMemo(() => plotBounds(graph, width, PLOT_HEIGHT, GRAPH_AXIS_PAD), [graph, width]);
  const drawing = useMemo(() => plotDrawing(graph, theme.graphSeries), [graph, theme.graphSeries]);
  const axes = useMemo(() => plotAxes(graph), [graph]);
  const svg = (
    <GraphCanvas
      spec={axes}
      theme={theme}
      clipId={clipId}
      width={width}
      height={PLOT_HEIGHT}
      bounds={bounds}
      drawn={drawing.drawn}
      points={drawing.points}
      layers={drawing.layers}
    />
  );
  return (
    <View style={[styles.card, { width }]} testID="plot-graph">
      <View accessible accessibilityRole="image" accessibilityLabel={plotDescription(graph)}>
        {isSkiaAvailable() ? (
          <Suspense fallback={svg}>
            <SkiaPlot graph={graph} drawing={drawing} bounds={bounds} width={width} theme={theme} />
          </Suspense>
        ) : (
          svg
        )}
      </View>
      <Legend drawing={drawing} theme={theme} />
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
