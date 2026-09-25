/* eslint-disable react-hooks/immutability -- Reanimated shared values are mutated on the UI thread by design */
/** Native Skia trajectory chart with automatic UI-thread playback. */
import { useCallback, useEffect, useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import {
  Canvas,
  Circle,
  Group,
  Path,
  Skia,
  Text as SkiaText,
  useFont,
} from "@shopify/react-native-skia";
import {
  cancelAnimation,
  runOnJS,
  useDerivedValue,
  useSharedValue,
  withTiming,
} from "react-native-reanimated";

import {
  expandBoundsForAxes,
  formatGraphExpr,
  graphBounds,
  mapGraphPoint,
  type GraphSpec,
} from "@/lib/math/graphBlock";
import {
  playbackStart,
  remainingPlaybackDuration,
} from "@/lib/animationPlayback";
import { Icon } from "@/ui/icons/Icon";
import {
  trajectoryAxisLayout,
  trajectoryAxisCaptionPosition,
  trajectoryPointAt,
  type ScreenPoint,
} from "@/lib/math/trajectory";
import { Motion, useReduceMotion } from "@/lib/motion";
import { Theme } from "@/lib/theme";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";

/** Changing either breaks TrajectoryGraphTicks.test.tsx, which pins tick geometry. */
export const TRAJECTORY_PAD = 40;
export const TRAJECTORY_CHART_HEIGHT = 220;

const DOT_RADIUS = 5.5;
const ARROW_LENGTH = 34;
const ARROW_HEAD = 6;
const TICK_FONT_SIZE = 11;

type Props = {
  spec: GraphSpec;
  chartWidth: number;
  styles: { wrap: object; title: object };
  theme: Theme;
};

function pointsPath(points: readonly ScreenPoint[]) {
  const path = Skia.Path.Make();
  points.forEach((point, index) => {
    if (index === 0) path.moveTo(point.px, point.py);
    else path.lineTo(point.px, point.py);
  });
  return path;
}

function partialPointsPath(points: readonly ScreenPoint[], progress: number) {
  "worklet";
  const path = Skia.Path.Make();
  if (points.length === 0) return path;
  const clamped = Math.max(0, Math.min(1, progress));
  const at = clamped * (points.length - 1);
  const end = Math.floor(at);
  path.moveTo(points[0].px, points[0].py);
  for (let index = 1; index <= end; index += 1) {
    path.lineTo(points[index].px, points[index].py);
  }
  if (end < points.length - 1) {
    const fraction = at - end;
    const a = points[end];
    const b = points[end + 1];
    path.lineTo(
      a.px + (b.px - a.px) * fraction,
      a.py + (b.py - a.py) * fraction,
    );
  }
  return path;
}

function linePath(x1: number, y1: number, x2: number, y2: number) {
  const path = Skia.Path.Make();
  path.moveTo(x1, y1);
  path.lineTo(x2, y2);
  return path;
}

function arrowPath(x1: number, y1: number, x2: number, y2: number) {
  const path = linePath(x1, y1, x2, y2);
  const dx = x2 - x1;
  const dy = y2 - y1;
  const length = Math.hypot(dx, dy) || 1;
  const ux = dx / length;
  const uy = dy / length;
  path.moveTo(x2, y2);
  path.lineTo(
    x2 - ux * ARROW_HEAD + uy * ARROW_HEAD * 0.6,
    y2 - uy * ARROW_HEAD - ux * ARROW_HEAD * 0.6,
  );
  path.moveTo(x2, y2);
  path.lineTo(
    x2 - ux * ARROW_HEAD - uy * ARROW_HEAD * 0.6,
    y2 - uy * ARROW_HEAD + ux * ARROW_HEAD * 0.6,
  );
  return path;
}

function motionArrowPaths(points: readonly ScreenPoint[]) {
  if (points.length < 2) return [];
  const start = points[0];
  const next = points[Math.max(1, Math.round((points.length - 1) * 0.04))];
  const apex = points.reduce((best, point) => (point.py < best.py ? point : best), points[0]);
  const dx = next.px - start.px;
  const dy = next.py - start.py;
  const length = Math.hypot(dx, dy) || 1;
  return [
    arrowPath(
      start.px,
      start.py,
      start.px + (dx / length) * ARROW_LENGTH,
      start.py + (dy / length) * ARROW_LENGTH,
    ),
    arrowPath(apex.px, apex.py, apex.px, apex.py + ARROW_LENGTH),
  ];
}

export function TrajectoryChart({ spec, chartWidth, styles, theme }: Props) {
  const { t } = useTranslation();
  const reduceMotion = useReduceMotion();
  const progress = useSharedValue(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const font = useFont(require("../../assets/fonts/SpaceMono-Regular.ttf"), TICK_FONT_SIZE);

  const bounds = useMemo(
    () => expandBoundsForAxes(graphBounds(spec.points), { pad: false }),
    [spec.points],
  );
  const screenPoints = useMemo(
    () =>
      spec.points.map(([x, y]) =>
        mapGraphPoint(x, y, bounds, chartWidth, TRAJECTORY_CHART_HEIGHT, TRAJECTORY_PAD),
      ),
    [spec.points, bounds, chartWidth],
  );
  const curvePath = useMemo(() => pointsPath(screenPoints), [screenPoints]);
  const axes = useMemo(
    () => trajectoryAxisLayout(bounds, chartWidth, TRAJECTORY_CHART_HEIGHT, TRAJECTORY_PAD),
    [bounds, chartWidth],
  );
  const gridPath = useMemo(() => {
    const path = Skia.Path.Make();
    axes.xTicks.forEach((tick) => {
      path.moveTo(tick.px, TRAJECTORY_PAD);
      path.lineTo(tick.px, TRAJECTORY_CHART_HEIGHT - TRAJECTORY_PAD);
    });
    axes.yTicks.forEach((tick) => {
      path.moveTo(TRAJECTORY_PAD, tick.py - 4);
      path.lineTo(chartWidth - TRAJECTORY_PAD, tick.py - 4);
    });
    return path;
  }, [axes, chartWidth]);
  const axesPath = useMemo(() => {
    const path = Skia.Path.Make();
    path.moveTo(axes.yAxisX, TRAJECTORY_PAD);
    path.lineTo(axes.yAxisX, TRAJECTORY_CHART_HEIGHT - TRAJECTORY_PAD);
    path.moveTo(TRAJECTORY_PAD, axes.xAxisY);
    path.lineTo(chartWidth - TRAJECTORY_PAD, axes.xAxisY);
    return path;
  }, [axes, chartWidth]);
  const clip = useMemo(
    () =>
      Skia.XYWHRect(
        TRAJECTORY_PAD,
        TRAJECTORY_PAD,
        Math.max(0, chartWidth - TRAJECTORY_PAD * 2),
        TRAJECTORY_CHART_HEIGHT - TRAJECTORY_PAD * 2,
      ),
    [chartWidth],
  );

  const markStopped = useCallback(() => setIsPlaying(false), []);
  const play = useCallback(() => {
    cancelAnimation(progress);
    const start = playbackStart(progress.value);
    progress.value = start;
    setIsPlaying(true);
    progress.value = withTiming(
      1,
      {
        duration: remainingPlaybackDuration(Motion.duration.trajectory, start),
        easing: Motion.easing.linear,
      },
      (finished) => {
        if (finished) runOnJS(markStopped)();
      },
    );
  }, [markStopped, progress]);
  const pause = useCallback(() => {
    cancelAnimation(progress);
    setIsPlaying(false);
  }, [progress]);

  useEffect(() => {
    if (reduceMotion) return;
    play();
    return () => cancelAnimation(progress);
  }, [play, progress, reduceMotion]);

  const trailPath = useDerivedValue(() => partialPointsPath(screenPoints, progress.value));
  const dotX = useDerivedValue(() => trajectoryPointAt(screenPoints, progress.value).px);
  const dotY = useDerivedValue(() => trajectoryPointAt(screenPoints, progress.value).py);
  const xLabel = spec.x_label ?? "x";
  const yLabel = spec.y_label ?? "y";
  const title = formatGraphExpr(spec.title ?? "Trajectory");
  const spatial = spec.trajectory_type === "parametric";
  const arrowPaths = useMemo(
    () => (spatial ? motionArrowPaths(screenPoints) : []),
    [screenPoints, spatial],
  );
  const measure = useCallback(
    (value: string) => font?.measureText(value).width ?? value.length * 6.7,
    [font],
  );
  const xCaption = trajectoryAxisCaptionPosition(
    measure(xLabel),
    chartWidth,
    TRAJECTORY_CHART_HEIGHT,
    TRAJECTORY_PAD,
  );

  return (
    <View style={styles.wrap}>
      <Text style={styles.title}>{title}</Text>
      <View style={{ width: chartWidth, height: TRAJECTORY_CHART_HEIGHT }}>
        <Canvas
          testID="trajectory-canvas"
          style={{ width: chartWidth, height: TRAJECTORY_CHART_HEIGHT }}
        >
          <Path path={gridPath} color={theme.border} style="stroke" strokeWidth={1} />
          <Path path={axesPath} color={theme.textSecondary} style="stroke" strokeWidth={1.25} />
          {font
            ? axes.xTicks.map((tick) => (
                <SkiaText
                  key={`x-${tick.value}`}
                  x={tick.px - measure(tick.text) / 2}
                  y={tick.py}
                  text={tick.text}
                  font={font}
                  color={theme.textSecondary}
                />
              ))
            : null}
          {font
            ? axes.yTicks.map((tick) => (
                <SkiaText
                  key={`y-${tick.value}`}
                  x={Math.max(4, tick.px - measure(tick.text))}
                  y={tick.py}
                  text={tick.text}
                  font={font}
                  color={theme.textSecondary}
                />
              ))
            : null}
          {font &&
          bounds.xMin <= 0 &&
          bounds.xMax >= 0 &&
          bounds.yMin <= 0 &&
          bounds.yMax >= 0 ? (
            <SkiaText
              x={axes.origin.px + 10}
              y={axes.origin.py + 16}
              text="0"
              font={font}
              color={theme.textSecondary}
            />
          ) : null}
          {font ? (
            <>
              <SkiaText
                x={xCaption.px}
                y={xCaption.py}
                text={xLabel}
                font={font}
                color={theme.textSecondary}
              />
              <SkiaText
                x={TRAJECTORY_PAD}
                y={TRAJECTORY_PAD - 10}
                text={yLabel}
                font={font}
                color={theme.textSecondary}
              />
            </>
          ) : null}
          <Group clip={clip}>
            {!reduceMotion ? (
              <Path
                path={trailPath}
                color={theme.primary}
                style="stroke"
                strokeWidth={7}
                strokeCap="round"
                strokeJoin="round"
                opacity={0.25}
              />
            ) : null}
            <Path
              path={curvePath}
              color={theme.primary}
              style="stroke"
              strokeWidth={2.5}
              strokeCap="round"
              strokeJoin="round"
            />
            {arrowPaths.map((path, index) => (
              <Path
                key={`arrow-${index}`}
                path={path}
                color={index === 0 ? theme.primary : theme.textSecondary}
                style="stroke"
                strokeWidth={1.5}
              />
            ))}
          </Group>
          {!reduceMotion ? (
            <>
              <Circle cx={dotX} cy={dotY} r={DOT_RADIUS + 1.5} color={theme.bg} />
              <Circle cx={dotX} cy={dotY} r={DOT_RADIUS} color={theme.primary} />
            </>
          ) : null}
        </Canvas>
        {spatial ? (
          <View testID="trajectory-arrows" pointerEvents="none" style={localStyles.marker} />
        ) : null}
      </View>
      {!reduceMotion ? (
        <Pressable
          testID="trajectory-control"
          accessibilityRole="button"
          accessibilityLabel={t(
            isPlaying ? "rich.simulation_pause_a11y" : "rich.simulation_play_a11y",
          )}
          onPress={isPlaying ? pause : play}
          style={({ pressed }) => [
            localStyles.control,
            { borderColor: theme.border, opacity: pressed ? 0.6 : 1 },
          ]}
        >
          <Icon
            testID={isPlaying ? "trajectory-stop-symbol" : "trajectory-play-symbol"}
            name={isPlaying ? "pause" : "play"}
            size={20}
            color={theme.primary}
          />
        </Pressable>
      ) : null}
    </View>
  );
}

const localStyles = StyleSheet.create({
  control: {
    marginTop: Space.xs,
    width: 36,
    height: 36,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: Radius.bubble,
    borderWidth: StyleSheet.hairlineWidth,
  },
  marker: {
    position: "absolute",
    width: 1,
    height: 1,
    opacity: 0,
  },
});
