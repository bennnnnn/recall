/**
 * The state behind a function plot card and its explorer: the series being
 * edited, the hole and mark points, the card's plot size and view, and the
 * explorer's plot size, view and samples. `InteractiveFunctionPlot` draws it.
 */
import { useCallback, useId, useMemo, useRef, useState } from "react";
import { useWindowDimensions, type LayoutChangeEvent, type ScrollViewInstance } from "react-native";
import { useSafeAreaInsets, type EdgeInsets } from "react-native-safe-area-context";

import { GRAPH_AXIS_PAD } from "@/components/rich/GraphCanvas";
import { markLabel, type GraphPoints } from "@/components/rich/graphPoints";
import { MODAL_PLOT_MIN } from "@/components/rich/ExplorerModal";
import {
  drawGraphSeries,
  useGraphSeries,
  useGraphViewport,
  type GraphSeriesState,
} from "@/hooks/useInteractiveGraph";
import { useSkiaGraphViewport } from "@/hooks/useSkiaGraphViewport";
import { interactiveFunctionBounds } from "@/lib/math/graphFit";
import { type GraphSpec } from "@/lib/math/graphSpec";
import { expandGraphView } from "@/lib/math/graphViewport";
import { isSkiaAvailable } from "@/lib/skiaAvailability";
import { Space } from "@/lib/space";
import type { Theme } from "@/lib/theme";

export const CHART_HEIGHT = 220;
export const GRAPH_CARD_INSET = Space.sm;
/** Skia explorer samples a 3x window at 3x density for mid-gesture runway. */
const SKIA_SAMPLE_EXPAND = 3;
const SKIA_SAMPLES = 480;

/** What both plots draw: the series, their colours and the plotted variable. */
type Curves = { series: GraphSeriesState[]; palette: readonly string[]; variable: string };

function hasCurve2(spec: GraphSpec): boolean {
  return spec.type === "function" && !!spec.expr2 && !!spec.points2?.length;
}

/**
 * Open points and the server's marked points on a seeded curve, while it is shown and
 * still the server's expression: an edited curve is no longer the one SymPy read.
 */
function useGraphPoints(spec: GraphSpec, { series, palette }: Curves): GraphPoints {
  return useMemo<GraphPoints>(() => {
    const points: GraphPoints = { holes: [], marks: [] };
    if (spec.type !== "function") return points;
    const seeded = (curve: 1 | 2) => {
      const row = series[curve - 1];
      return row?.visible && row.seedExpr === row.expr ? palette[(curve - 1) % palette.length] : null;
    };
    const holes: [1 | 2, [number, number][] | undefined][] = [[1, spec.holes], [2, spec.holes2]];
    for (const [curve, list] of holes) {
      const color = seeded(curve);
      if (color) for (const point of list ?? []) points.holes.push({ point, color });
    }
    for (const { x, y, label, curve } of spec.marks ?? []) {
      const color = seeded(curve);
      if (color) points.marks.push({ point: [x, y], color, label: markLabel(x, y, label) });
    }
    return points;
  }, [palette, series, spec]);
}

/** The card's plot: its laid-out width, its view and the curves sampled for it. */
function useCardPlot(spec: GraphSpec, chartWidth: number, { series, palette, variable }: Curves) {
  const [plotWidth, setPlotWidth] = useState(
    Math.max(1, chartWidth - GRAPH_CARD_INSET * 2),
  );
  const cardWidth = Math.max(1, plotWidth);
  const cardAspect = (cardWidth - GRAPH_AXIS_PAD * 2) / (CHART_HEIGHT - GRAPH_AXIS_PAD * 2 || 1);
  const cardBounds = useMemo(
    () => interactiveFunctionBounds(spec, cardAspect),
    [cardAspect, spec],
  );
  const ignoreCardCommit = useCallback(() => {}, []);
  const cardSkiaViewport = useSkiaGraphViewport({
    width: cardWidth,
    height: CHART_HEIGHT,
    pad: GRAPH_AXIS_PAD,
    initialView: cardBounds,
    onCommit: ignoreCardCommit,
  });
  const cardDrawn = useMemo(
    () => series.map((row, i) => drawGraphSeries(row, palette[i % palette.length], variable, cardBounds)),
    [cardBounds, palette, series, variable],
  );
  const onCardLayout = (e: LayoutChangeEvent) => {
    const w = Math.round(e.nativeEvent.layout.width - GRAPH_CARD_INSET * 2);
    if (w > 0 && w !== plotWidth) setPlotWidth(w);
  };
  return { width: cardWidth, bounds: cardBounds, drawn: cardDrawn, skiaViewport: cardSkiaViewport, onLayout: onCardLayout };
}

/** The explorer's plot: its laid-out size, its pinch-and-pan view and the curves sampled for it. */
function useExplorerPlot(
  spec: GraphSpec,
  insets: EdgeInsets,
  skiaExplorer: boolean,
  { series, palette, variable }: Curves,
) {
  const { width: screenW, height: screenH } = useWindowDimensions();
  const modalWidth = Math.max(1, screenW - insets.left - insets.right);
  const fallbackModalH = Math.max(MODAL_PLOT_MIN, screenH - insets.top - insets.bottom - 200);
  const [modalPlot, setModalPlot] = useState({ width: modalWidth, height: fallbackModalH });
  // The view's shape is the plot's tallest laid-out size in this window: the keyboard
  // shrinks the plot while a function is typed (ExplorerModal), and a view re-made for each
  // height threw the user's pan and zoom away. The tallest, not the first: opened while a
  // keyboard was still closing, the plot's first layout is short (review, 2026-11-09).
  const screen = `${screenW}x${screenH}`;
  const [viewShape, setViewShape] = useState<{ screen: string; width: number; height: number } | null>(null);
  const shape = viewShape?.screen === screen ? viewShape : modalPlot;
  const modalAspect = (shape.width - GRAPH_AXIS_PAD * 2) / (shape.height - GRAPH_AXIS_PAD * 2 || 1);
  const modalInitialView = useMemo(
    () => interactiveFunctionBounds(spec, modalAspect),
    [modalAspect, spec],
  );
  const viewport = useGraphViewport({
    width: modalPlot.width,
    height: modalPlot.height,
    pad: GRAPH_AXIS_PAD,
    initialView: modalInitialView,
  });
  const onModalPlotLayout = (e: LayoutChangeEvent) => {
    const { width, height } = e.nativeEvent.layout;
    const w = Math.round(width);
    const h = Math.round(height);
    if (w > 0 && h > 0 && (w !== modalPlot.width || h !== modalPlot.height)) {
      setModalPlot({ width: w, height: h });
    }
    const taller = viewShape?.screen !== screen || h > viewShape.height;
    if (w > 0 && h > 0 && taller) setViewShape({ screen, width: w, height: h });
  };
  // The Skia explorer pans/zooms on the UI thread against samples taken over
  // an expanded window; viewport.bounds only moves on gesture-end commits.
  const sampleBounds = useMemo(
    () => (skiaExplorer ? expandGraphView(viewport.bounds, SKIA_SAMPLE_EXPAND) : viewport.bounds),
    [skiaExplorer, viewport.bounds],
  );
  const modalDrawn = useMemo(
    () =>
      series.map((row, i) =>
        drawGraphSeries(
          row,
          palette[i % palette.length],
          variable,
          sampleBounds,
          skiaExplorer ? SKIA_SAMPLES : 160,
        ),
      ),
    [palette, series, variable, sampleBounds, skiaExplorer],
  );
  return {
    plot: modalPlot,
    onPlotLayout: onModalPlotLayout,
    initialView: modalInitialView,
    viewport,
    drawn: modalDrawn,
  };
}

export function useFunctionPlotState(spec: GraphSpec, chartWidth: number, theme: Theme) {
  const insets = useSafeAreaInsets();
  const [open, setOpen] = useState(false);
  const closeExplorer = useCallback(() => setOpen(false), []);
  const cardClipId = useId().replace(/:/g, "");
  const modalClipId = useId().replace(/:/g, "");
  const seedExprs = hasCurve2(spec) ? [spec.expr, spec.expr2 ?? ""] : [spec.expr];
  const seedFallbacks = hasCurve2(spec)
    ? [
        { points: spec.points, segments: spec.segments },
        { points: spec.points2 ?? [], segments: spec.segments2 },
      ]
    : [{ points: spec.points, segments: spec.segments }];
  const { series, canAdd, setExpr, toggleVisible, removeSeries, addSeries } = useGraphSeries(
    seedExprs,
    seedFallbacks,
  );
  const curves: Curves = { series, palette: theme.graphSeries, variable: spec.variable ?? "x" };
  const points = useGraphPoints(spec, curves);
  const card = useCardPlot(spec, chartWidth, curves);
  const skia = isSkiaAvailable();
  const explorer = useExplorerPlot(spec, insets, skia, curves);
  const seriesListRef = useRef<ScrollViewInstance>(null);
  const addSeriesAndReveal = () => {
    addSeries();
    requestAnimationFrame(() => {
      seriesListRef.current?.scrollToEnd({ animated: true });
    });
  };

  return {
    open,
    openExplorer: () => setOpen(true),
    closeExplorer,
    insets,
    skia,
    verticalX: spec.type === "vertical" ? spec.x : undefined,
    points,
    editor: { canAdd, setExpr, toggleVisible, removeSeries, addSeries, addSeriesAndReveal, seriesListRef },
    card: { ...card, clipId: cardClipId },
    explorer: { ...explorer, clipId: modalClipId },
  };
}
