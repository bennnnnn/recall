import { useCallback, useMemo, useRef, useState } from "react";
import { Gesture } from "react-native-gesture-handler";
import { runOnJS } from "react-native-reanimated";

import { unmapGraphPoint } from "@/lib/graphBlock";
import {
  displayGraphExpr,
  parseGraphExpr,
  sampleGraphExpr,
} from "@/lib/graphExpr";
import {
  defaultInteractiveBounds,
  panGraphView,
  zoomGraphView,
  type GraphView,
} from "@/lib/graphViewport";

export const MAX_GRAPH_SERIES = 4;
const SCATTER_MAX_POINTS = 20;

export type SampledCurve = {
  points: [number, number][];
  segments?: [number, number][][];
};

export type GraphSeriesState = {
  id: string;
  expr: string;
  visible: boolean;
  /** Original verified function — cannot be removed. */
  locked: boolean;
  seedExpr?: string;
  fallback?: SampledCurve;
};

export type DrawnSeries = GraphSeriesState & {
  color: string;
  points: [number, number][];
  segments?: [number, number][][];
  invalid: boolean;
};

export function sampleInView(
  expr: string,
  variable: string,
  bounds: GraphView,
): SampledCurve | null {
  const node = parseGraphExpr(expr, variable);
  if (!node) return null;
  const padX = (bounds.xMax - bounds.xMin) * 0.02;
  return sampleGraphExpr(node, bounds.xMin - padX, bounds.xMax + padX, 160);
}

export function seedGraphSeries(
  exprs: string[],
  fallbacks: (SampledCurve | undefined)[] = [],
): GraphSeriesState[] {
  const out: GraphSeriesState[] = [];
  for (let i = 0; i < exprs.length && i < MAX_GRAPH_SERIES; i += 1) {
    const raw = exprs[i]?.trim() ?? "";
    if (!raw && i > 0) continue;
    out.push({
      id: String(i),
      expr: displayGraphExpr(raw),
      visible: true,
      locked: i === 0,
      seedExpr: displayGraphExpr(raw),
      fallback: fallbacks[i],
    });
  }
  if (out.length === 0) {
    out.push({ id: "0", expr: "", visible: true, locked: true });
  }
  return out;
}

export function drawGraphSeries(
  series: GraphSeriesState,
  color: string,
  variable: string,
  bounds: GraphView,
): DrawnSeries {
  const sampled = series.expr.trim() ? sampleInView(series.expr, variable, bounds) : null;
  const dirty =
    series.seedExpr != null &&
    displayGraphExpr(series.expr) !== displayGraphExpr(series.seedExpr);
  const fallback = series.fallback;
  // Sparse samples keep server points; relations (ellipse) cannot eval as y=f(x).
  const useFallback =
    fallback != null &&
    !dirty &&
    (fallback.points.length <= SCATTER_MAX_POINTS || sampled == null);
  const points = useFallback ? fallback.points : (sampled?.points ?? []);
  const segments = useFallback ? fallback.segments : sampled?.segments;
  const invalid =
    series.expr.trim().length > 0 &&
    !useFallback &&
    !(sampled != null && sampled.points.length > 0);
  return { ...series, color, points, segments, invalid };
}

export function useGraphSeries(
  seedExprs: string[],
  seedFallbacks: (SampledCurve | undefined)[] = [],
) {
  const [series, setSeries] = useState(() => seedGraphSeries(seedExprs, seedFallbacks));
  const nextId = useRef(series.length);

  const setExpr = useCallback((id: string, expr: string) => {
    setSeries((prev) => prev.map((row) => (row.id === id ? { ...row, expr } : row)));
  }, []);

  const toggleVisible = useCallback((id: string) => {
    setSeries((prev) =>
      prev.map((row) => (row.id === id ? { ...row, visible: !row.visible } : row)),
    );
  }, []);

  const removeSeries = useCallback((id: string) => {
    setSeries((prev) => prev.filter((row) => row.id !== id || row.locked));
  }, []);

  const addSeries = useCallback(() => {
    setSeries((prev) => {
      if (prev.length >= MAX_GRAPH_SERIES) return prev;
      const id = String(nextId.current);
      nextId.current += 1;
      return [...prev, { id, expr: "", visible: true, locked: false }];
    });
  }, []);

  return {
    series,
    canAdd: series.length < MAX_GRAPH_SERIES,
    setExpr,
    toggleVisible,
    removeSeries,
    addSeries,
  };
}

type ViewportArgs = {
  width: number;
  height: number;
  pad: number;
};

export function useGraphViewport({ width, height, pad }: ViewportArgs) {
  const plotAspect = (width - pad * 2) / (height - pad * 2 || 1);
  const initialView = useMemo(
    () => defaultInteractiveBounds(plotAspect),
    [plotAspect],
  );
  const [bounds, setBounds] = useState<GraphView>(initialView);
  const boundsRef = useRef(bounds);
  boundsRef.current = bounds;
  const startRef = useRef(bounds);

  const captureStart = useCallback(() => {
    startRef.current = boundsRef.current;
  }, []);

  const applyPinch = useCallback(
    (scale: number, focalX: number, focalY: number) => {
      const start = startRef.current;
      const focal = unmapGraphPoint(focalX, focalY, start, width, height, pad);
      setBounds(zoomGraphView(start, scale, focal.x, focal.y));
    },
    [height, pad, width],
  );

  const applyPan = useCallback(
    (dx: number, dy: number) => {
      setBounds(panGraphView(startRef.current, dx, dy, width, height, pad));
    },
    [height, pad, width],
  );

  const resetView = useCallback(() => setBounds(initialView), [initialView]);

  const gesture = useMemo(() => {
    // Pinch must not sit behind Exclusive(doubleTap, …) — that waits for a
    // second tap timeout and the in-chat FlashList never receives the pinch.
    const pinch = Gesture.Pinch()
      .onBegin(() => {
        runOnJS(captureStart)();
      })
      .onUpdate((e) => {
        runOnJS(applyPinch)(e.scale, e.focalX, e.focalY);
      });
    const pan = Gesture.Pan()
      .minDistance(10)
      .maxPointers(1)
      .onBegin(() => {
        runOnJS(captureStart)();
      })
      .onUpdate((e) => {
        runOnJS(applyPan)(e.translationX, e.translationY);
      });
    const doubleTap = Gesture.Tap()
      .numberOfTaps(2)
      .onEnd(() => {
        runOnJS(resetView)();
      });
    return Gesture.Simultaneous(pinch, pan, doubleTap);
  }, [applyPan, applyPinch, captureStart, resetView]);

  return { bounds, gesture, resetView };
}
