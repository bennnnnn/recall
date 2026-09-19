/**
 * Skia graph explorer — the full-screen modal canvas. Bounds live in a
 * Reanimated shared value and every path/label below is a derived value, so
 * pinch/pan/trace render on the UI thread with no React re-render per frame.
 * Loaded lazily and only when isSkiaAvailable() — the SVG explorer stays the
 * fallback for Expo Go and stale dev clients.
 */
import { GestureDetector } from "react-native-gesture-handler";
import {
  Canvas,
  Circle,
  DashPathEffect,
  Group,
  Path,
  RoundedRect,
  Skia,
  Text as SkiaText,
  useFont,
  type SkFont,
} from "@shopify/react-native-skia";
import { runOnJS, useAnimatedReaction, useDerivedValue } from "react-native-reanimated";

import type { DrawnSeries } from "@/hooks/useInteractiveGraph";
import type { useSkiaGraphViewport } from "@/hooks/useSkiaGraphViewport";
import { selection } from "@/lib/haptics";
import {
  axisTicksW,
  formatShortW,
  formatTickW,
  mapPointW,
  nearestSampleW,
  unmapPointW,
  type GraphViewW,
} from "@/lib/math/graphWorklets";
import type { Theme } from "@/lib/theme";

const MAX_SERIES_PATHS = 4;
const AXIS_SLOTS = 16;
const TICK_FONT_SIZE = 11;
/** SpaceMono advance at 11pt — callout sizing without a font round-trip. */
const MONO_CHAR_PX = 6.7;
const MARKER_RADIUS = 4;
const SLOT_INDICES = Array.from({ length: AXIS_SLOTS }, (_, i) => i);
const SERIES_INDICES = Array.from({ length: MAX_SERIES_PATHS }, (_, i) => i);

type Viewport = ReturnType<typeof useSkiaGraphViewport>;

type TickLabel = { px: number; py: number; text: string };

type Chrome = {
  grid: ReturnType<typeof Skia.Path.Make>;
  axes: ReturnType<typeof Skia.Path.Make>;
  xLabels: TickLabel[];
  yLabels: TickLabel[];
  origin: { px: number; py: number };
  originInView: boolean;
  xNamePos: { px: number; py: number };
  yNamePos: { px: number; py: number };
};

function buildSeriesPath(
  row: DrawnSeries | undefined,
  b: GraphViewW,
  width: number,
  height: number,
  pad: number,
) {
  "worklet";
  const path = Skia.Path.Make();
  if (!row || !row.visible) return path;
  const segs = row.segments?.filter((seg) => seg.length >= 2);
  const curves = segs && segs.length > 1 ? segs : row.points.length >= 2 ? [row.points] : [];
  for (const seg of curves) {
    let started = false;
    for (const [x, y] of seg) {
      if (!Number.isFinite(x) || !Number.isFinite(y)) {
        started = false;
        continue;
      }
      const { px, py } = mapPointW(x, y, b, width, height, pad);
      if (started) path.lineTo(px, py);
      else {
        path.moveTo(px, py);
        started = true;
      }
    }
  }
  return path;
}

function buildFillPath(
  row: DrawnSeries | undefined,
  b: GraphViewW,
  width: number,
  height: number,
  pad: number,
) {
  "worklet";
  const path = Skia.Path.Make();
  if (!row || !row.visible || row.cmp === "=") return path;
  const segs = row.segments?.filter((seg) => seg.length >= 2);
  const curve = segs && segs.length > 1 ? segs[0] : row.points.length >= 2 ? row.points : null;
  if (!curve) return path;
  const below = row.cmp === "<" || row.cmp === "<=";
  const edgePy = below ? height - pad : pad;
  let started = false;
  let firstPx = 0;
  let lastPx = 0;
  for (const [x, y] of curve) {
    if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
    const { px, py } = mapPointW(x, y, b, width, height, pad);
    if (!started) {
      path.moveTo(px, py);
      firstPx = px;
      started = true;
    } else {
      path.lineTo(px, py);
    }
    lastPx = px;
  }
  if (started) {
    path.lineTo(lastPx, edgePy);
    path.lineTo(firstPx, edgePy);
    path.close();
  }
  return path;
}

function buildMarkerPath(
  drawn: DrawnSeries[],
  b: GraphViewW,
  width: number,
  height: number,
  pad: number,
) {
  "worklet";
  const path = Skia.Path.Make();
  const visible = drawn.filter((row) => row.visible);
  if (visible.length !== 1) return path;
  const points = visible[0].points;
  if (points.length > 20) return path;
  for (const [x, y] of points) {
    if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
    if (x < b.xMin || x > b.xMax || y < b.yMin || y > b.yMax) continue;
    const { px, py } = mapPointW(x, y, b, width, height, pad);
    path.addCircle(px, py, MARKER_RADIUS);
  }
  return path;
}

function computeChrome(
  b: GraphViewW,
  width: number,
  height: number,
  pad: number,
  font: SkFont | null,
): Chrome {
  "worklet";
  const measure = (text: string) =>
    font ? font.measureText(text).width : text.length * MONO_CHAR_PX;
  const grid = Skia.Path.Make();
  const axes = Skia.Path.Make();
  const origin = mapPointW(0, 0, b, width, height, pad);

  const xLabels: TickLabel[] = [];
  for (const n of axisTicksW(b.xMin, b.xMax)) {
    if (Math.abs(n) < 1e-9) continue;
    const { px } = mapPointW(n, 0, b, width, height, pad);
    grid.moveTo(px, pad);
    grid.lineTo(px, height - pad);
    if (xLabels.length < AXIS_SLOTS) {
      const text = formatTickW(n);
      xLabels.push({ px: px - measure(text) / 2, py: origin.py + 16, text });
    }
  }
  const yLabels: TickLabel[] = [];
  for (const n of axisTicksW(b.yMin, b.yMax)) {
    if (Math.abs(n) < 1e-9) continue;
    const { py } = mapPointW(0, n, b, width, height, pad);
    grid.moveTo(pad, py);
    grid.lineTo(width - pad, py);
    if (py >= pad + 12 && yLabels.length < AXIS_SLOTS) {
      const text = formatTickW(n);
      yLabels.push({ px: Math.max(4, origin.px - 6 - measure(text)), py: py + 4, text });
    }
  }

  axes.moveTo(origin.px, pad);
  axes.lineTo(origin.px, height - pad);
  axes.moveTo(pad, origin.py);
  axes.lineTo(width - pad, origin.py);

  const originInView = b.xMin <= 0 && b.xMax >= 0 && b.yMin <= 0 && b.yMax >= 0;
  return {
    grid,
    axes,
    xLabels,
    yLabels,
    origin,
    originInView,
    xNamePos: { px: width - pad, py: origin.py - 8 },
    yNamePos: { px: Math.max(origin.px + 8, 4), py: pad + 4 },
  };
}

function TickText({
  chrome,
  axis,
  index,
  font,
  color,
}: {
  chrome: { value: Chrome };
  axis: "xLabels" | "yLabels";
  index: number;
  font: SkFont;
  color: string;
}) {
  const x = useDerivedValue(() => chrome.value[axis][index]?.px ?? -1000);
  const y = useDerivedValue(() => chrome.value[axis][index]?.py ?? -1000);
  const text = useDerivedValue(() => chrome.value[axis][index]?.text ?? "");
  return <SkiaText x={x} y={y} text={text} font={font} color={color} />;
}

export function SkiaGraphExplorer({
  drawn,
  verticalX,
  xName = "x",
  yName = "y",
  width,
  height,
  pad,
  theme,
  viewport,
}: {
  drawn: DrawnSeries[];
  verticalX?: number;
  xName?: string;
  yName?: string;
  width: number;
  height: number;
  pad: number;
  theme: Theme;
  viewport: Viewport;
}) {
  const font = useFont(
    require("../../../assets/fonts/SpaceMono-Regular.ttf"),
    TICK_FONT_SIZE,
  );
  const { bounds, gesture, traceActive, tracePos } = viewport;
  const clip = Skia.XYWHRect(
    pad,
    pad,
    Math.max(0, width - pad * 2),
    Math.max(0, height - pad * 2),
  );

  const chrome = useDerivedValue(
    () => computeChrome(bounds.value, width, height, pad, font),
    [width, height, pad, font],
  );

  const seriesPaths = SERIES_INDICES.map((i) =>
    // eslint-disable-next-line react-hooks/rules-of-hooks -- fixed-length loop
    useDerivedValue(
      () => buildSeriesPath(drawn[i], bounds.value, width, height, pad),
      [drawn, width, height, pad],
    ),
  );
  const fillPaths = SERIES_INDICES.map((i) =>
    // eslint-disable-next-line react-hooks/rules-of-hooks -- fixed-length loop
    useDerivedValue(
      () => buildFillPath(drawn[i], bounds.value, width, height, pad),
      [drawn, width, height, pad],
    ),
  );
  const markerPath = useDerivedValue(
    () => buildMarkerPath(drawn, bounds.value, width, height, pad),
    [drawn, width, height, pad],
  );
  const verticalPath = useDerivedValue(() => {
    const path = Skia.Path.Make();
    if (verticalX == null) return path;
    const { px } = mapPointW(verticalX, 0, bounds.value, width, height, pad);
    path.moveTo(px, pad);
    path.lineTo(px, height - pad);
    return path;
  }, [verticalX, width, height, pad]);

  const trace = useDerivedValue(() => {
    if (!traceActive.value) return null;
    const b = bounds.value;
    const finger = unmapPointW(tracePos.value.px, tracePos.value.py, b, width, height, pad);
    const row = drawn.find((r) => r.visible && r.points.length > 1);
    if (!row) return null;
    const snap = nearestSampleW(row.points, finger.x);
    if (!snap) return null;
    const { px, py } = mapPointW(snap.x, snap.y, b, width, height, pad);
    return { px, py, x: snap.x, y: snap.y, index: snap.index, color: row.color };
  }, [drawn, width, height, pad]);

  useAnimatedReaction(
    () => trace.value?.index ?? -1,
    (index, previous) => {
      if (index >= 0 && index !== previous) runOnJS(selection)();
    },
  );

  const traceLine = useDerivedValue(() => {
    const path = Skia.Path.Make();
    const t = trace.value;
    if (!t) return path;
    path.moveTo(t.px, pad);
    path.lineTo(t.px, height - pad);
    return path;
  });
  const traceX = useDerivedValue(() => trace.value?.px ?? -1000);
  const traceY = useDerivedValue(() => trace.value?.py ?? -1000);
  const traceColor = useDerivedValue(() => trace.value?.color ?? theme.primary);
  const callout = useDerivedValue(() => {
    const t = trace.value;
    if (!t) return { x: 0, y: 0, w: 0, h: 0, text: "", visible: false };
    const text = `(${formatShortW(t.x)}, ${formatShortW(t.y)})`;
    const w = text.length * MONO_CHAR_PX + 16;
    const h = 26;
    const x = Math.min(Math.max(t.px + 12, 4), width - w - 4);
    const y = Math.max(t.py - 38, 4);
    return { x, y, w, h, text, visible: true };
  }, [width]);
  const calloutX = useDerivedValue(() => callout.value.x);
  const calloutY = useDerivedValue(() => callout.value.y);
  const calloutW = useDerivedValue(() => callout.value.w);
  const calloutH = useDerivedValue(() => callout.value.h);
  const calloutText = useDerivedValue(() => callout.value.text);
  const calloutTextX = useDerivedValue(() => callout.value.x + 8);
  const calloutTextY = useDerivedValue(() => callout.value.y + 17);
  const calloutVisible = useDerivedValue(() => (callout.value.visible ? 1 : 0));

  const gridPath = useDerivedValue(() => chrome.value.grid);
  const axesPath = useDerivedValue(() => chrome.value.axes);
  const originText = useDerivedValue(() => {
    const c = chrome.value;
    return c.originInView ? { x: c.origin.px + 10, y: c.origin.py + 16 } : null;
  });
  const originX = useDerivedValue(() => originText.value?.x ?? -1000);
  const originY = useDerivedValue(() => originText.value?.y ?? -1000);
  const xNameX = useDerivedValue(
    () =>
      chrome.value.xNamePos.px -
      (font ? font.measureText(xName).width : xName.length * MONO_CHAR_PX),
  );
  const xNameY = useDerivedValue(() => chrome.value.xNamePos.py);
  const yNameX = useDerivedValue(() => chrome.value.yNamePos.px);
  const yNameY = useDerivedValue(() => chrome.value.yNamePos.py);

  return (
    <GestureDetector gesture={gesture}>
      <Canvas style={{ width, height }} testID="skia-graph-canvas">
        <Path path={gridPath} color={theme.border} style="stroke" strokeWidth={1} />
        <Path
          path={axesPath}
          color={theme.textSecondary}
          style="stroke"
          strokeWidth={1.25}
        />
        <Group clip={clip}>
          {verticalX != null ? (
            <Path
              path={verticalPath}
              color={theme.primary}
              style="stroke"
              strokeWidth={2.5}
              strokeCap="round"
            />
          ) : null}
          {SERIES_INDICES.map((i) => (
            <Path
              key={`fill-${i}`}
              path={fillPaths[i]}
              color={drawn[i]?.color ?? theme.primary}
              style="fill"
              opacity={0.16}
            />
          ))}
          {SERIES_INDICES.map((i) => (
            <Path
              key={`series-${i}`}
              path={seriesPaths[i]}
              color={drawn[i]?.color ?? theme.primary}
              style="stroke"
              strokeWidth={2.5}
              strokeCap="round"
              strokeJoin="round"
            >
              {drawn[i] && (drawn[i].cmp === "<" || drawn[i].cmp === ">") ? (
                <DashPathEffect intervals={[6, 5]} />
              ) : null}
            </Path>
          ))}
          <Path path={markerPath} color={drawn[0]?.color ?? theme.primary} style="fill" />
          <Path
            path={traceLine}
            color={theme.textTertiary}
            style="stroke"
            strokeWidth={1}
          />
          <Circle cx={traceX} cy={traceY} r={5.5} color={traceColor} />
          <Circle cx={traceX} cy={traceY} r={2.5} color={theme.bg} />
        </Group>
        {font
          ? SLOT_INDICES.map((i) => (
              <TickText
                key={`tx-${i}`}
                chrome={chrome}
                axis="xLabels"
                index={i}
                font={font}
                color={theme.textSecondary}
              />
            ))
          : null}
        {font
          ? SLOT_INDICES.map((i) => (
              <TickText
                key={`ty-${i}`}
                chrome={chrome}
                axis="yLabels"
                index={i}
                font={font}
                color={theme.textSecondary}
              />
            ))
          : null}
        {font ? <SkiaText x={originX} y={originY} text="0" font={font} color={theme.textSecondary} /> : null}
        {font ? (
          <SkiaText x={xNameX} y={xNameY} text={xName} font={font} color={theme.textSecondary} />
        ) : null}
        {font ? (
          <SkiaText x={yNameX} y={yNameY} text={yName} font={font} color={theme.textSecondary} />
        ) : null}
        <RoundedRect
          x={calloutX}
          y={calloutY}
          width={calloutW}
          height={calloutH}
          r={8}
          color={theme.text}
          opacity={calloutVisible}
        />
        {font ? (
          <SkiaText
            x={calloutTextX}
            y={calloutTextY}
            text={calloutText}
            font={font}
            color={theme.bg}
            opacity={calloutVisible}
          />
        ) : null}
      </Canvas>
    </GestureDetector>
  );
}
