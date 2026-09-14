/* eslint-disable react-hooks/immutability -- Reanimated shared values are mutated on the UI thread by design */
/**
 * Trajectory chart with an optional played-back dot.
 *
 * A still parabola shows a projectile's path but not that it is fast at
 * launch, slow at the apex and fast again coming down. That asymmetry is the
 * physics, so it is what the animation exists to show.
 *
 * The solver samples both trajectory kinds at uniform time steps
 * (`solve_kinematics` / `solve_projectile`, 100 points, constant `dt`). For
 * `parametric` neither axis is time — but the *index* still is, so walking the
 * array at a constant rate is already physically correct and the fast-slow-fast
 * arc falls out for free. Nothing here re-derives motion.
 *
 * This is the app's first animated SVG element. The established alternative —
 * animate a wrapping `Animated.View` and re-render the SVG from JS state, as
 * `CircularClockBlock` does once a second — does not survive 60fps: the whole
 * polyline string would be rebuilt every frame.
 */
import { useCallback, useEffect, useId, useMemo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import Svg, { Circle, G, Line, Polygon, Polyline } from "react-native-svg";
import Animated, {
  cancelAnimation,
  useAnimatedProps,
  useSharedValue,
  withTiming,
} from "react-native-reanimated";

import { CartesianAxes } from "@/components/rich/CartesianAxes";
import {
  expandBoundsForAxes,
  formatGraphExpr,
  graphBounds,
  graphPolylinePoints,
  mapGraphPoint,
  type GraphSpec,
} from "@/lib/math/graphBlock";
import {
  trajectoryPathLength,
  trajectoryPointAt,
  type ScreenPoint,
} from "@/lib/math/trajectory";
import { Motion, useReduceMotion } from "@/lib/motion";
import { Theme } from "@/lib/theme";

const AnimatedCircle = Animated.createAnimatedComponent(Circle);
const AnimatedPolyline = Animated.createAnimatedComponent(Polyline);

/** Changing either breaks TrajectoryGraphTicks.test.tsx, which pins tick geometry. */
export const TRAJECTORY_PAD = 28;
export const TRAJECTORY_CHART_HEIGHT = 220;

const DOT_RADIUS = 5.5;
const ARROW_LENGTH = 34;
const ARROW_HEAD = 6;

type Props = {
  spec: GraphSpec;
  chartWidth: number;
  styles: { wrap: object; title: object };
  theme: Theme;
};

export function TrajectoryChart({ spec, chartWidth, styles, theme }: Props) {
  const { t } = useTranslation();
  const reduceMotion = useReduceMotion();
  const clipId = useId().replace(/:/g, "");
  const progress = useSharedValue(0);

  const bounds = useMemo(
    () => expandBoundsForAxes(graphBounds(spec.points), { pad: false }),
    [spec.points],
  );
  const polyline = useMemo(
    () => graphPolylinePoints(spec.points, chartWidth, TRAJECTORY_CHART_HEIGHT, bounds),
    [spec.points, chartWidth, bounds],
  );

  // Screen coordinates, computed once. The worklet indexes this array rather
  // than mapping on every frame.
  const screenPoints = useMemo(
    () =>
      spec.points.map(([x, y]) =>
        mapGraphPoint(x, y, bounds, chartWidth, TRAJECTORY_CHART_HEIGHT, TRAJECTORY_PAD),
      ),
    [spec.points, bounds, chartWidth],
  );

  const pathLength = useMemo(() => trajectoryPathLength(screenPoints), [screenPoints]);

  // Replay from the start on every press: a finished run leaves the dot at the
  // end, so "play" and "replay" are the same action and need no second control.
  const play = useCallback(() => {
    cancelAnimation(progress);
    progress.value = 0;
    progress.value = withTiming(1, {
      duration: Motion.duration.trajectory,
      easing: Motion.easing.linear,
    });
  }, [progress]);

  // A row can be recycled mid-playback; FlashList keeps them mounted past the
  // viewport but not forever.
  useEffect(() => () => cancelAnimation(progress), [progress]);

  const dotProps = useAnimatedProps(() => {
    const at = trajectoryPointAt(screenPoints, progress.value);
    return { cx: at.px, cy: at.py };
  });

  // The trail is the same curve drawn progressively: one animated number, no
  // per-frame string building. Building `points` in the worklet would be the
  // obvious approach and the wrong one.
  const trailProps = useAnimatedProps(() => ({
    strokeDashoffset: pathLength * (1 - progress.value),
  }));

  const xLabel = spec.x_label ?? "x";
  const yLabel = spec.y_label ?? "y";
  const title = formatGraphExpr(spec.title ?? "Trajectory");
  // Arrows only where both axes are space. On a height- or velocity-vs-time
  // chart the x-axis is time, so a "downward gravity arrow" would point across
  // a time axis and actively mislead.
  const spatial = spec.trajectory_type === "parametric";

  return (
    <View style={styles.wrap}>
      <Text style={styles.title}>{title}</Text>
      <Svg width={chartWidth} height={TRAJECTORY_CHART_HEIGHT}>
        <CartesianAxes
          width={chartWidth}
          height={TRAJECTORY_CHART_HEIGHT}
          pad={TRAJECTORY_PAD}
          bounds={bounds}
          clipId={clipId}
          axisColor={theme.textSecondary}
          labelColor={theme.textSecondary}
          gridColor={theme.border}
          xName={xLabel}
          yName={yLabel}
          fractionalTicks
        />
        <G clipPath={`url(#${clipId})`}>
          {/* The curve itself never dims. Playback is an addition to the
              chart, not a precondition for reading it — most people will
              never tap play, and they must get exactly the graph they get
              today. The trail is a wider, translucent halo drawn *under* the
              curve, so before the first press the two are indistinguishable
              from the single static polyline this replaced. */}
          {!reduceMotion && (
            <AnimatedPolyline
              points={polyline}
              fill="none"
              stroke={theme.primary}
              strokeWidth={7}
              strokeOpacity={0.25}
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeDasharray={[pathLength, pathLength]}
              animatedProps={trailProps}
            />
          )}
          <Polyline
            points={polyline}
            fill="none"
            stroke={theme.primary}
            strokeWidth={2.5}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          {spatial && (
            <MotionArrows points={screenPoints} theme={theme} />
          )}
        </G>
        {!reduceMotion && (
          <AnimatedCircle
            r={DOT_RADIUS}
            fill={theme.primary}
            stroke={theme.bg}
            strokeWidth={1.5}
            animatedProps={dotProps}
          />
        )}
      </Svg>
      {!reduceMotion && (
        <Pressable
          testID="trajectory-play"
          accessibilityRole="button"
          accessibilityLabel={t("rich.graph_play_a11y")}
          onPress={play}
          style={({ pressed }) => [
            localStyles.playButton,
            { borderColor: theme.border, opacity: pressed ? 0.6 : 1 },
          ]}
        >
          <Text style={[localStyles.playLabel, { color: theme.primary }]}>
            {t("rich.graph_play")}
          </Text>
        </Pressable>
      )}
    </View>
  );
}

/**
 * Launch velocity and gravity, drawn once — both are constant, so neither
 * needs to animate. Gravity hangs from the apex; v0 leaves the launch point
 * along the direction the curve actually starts in.
 */
function MotionArrows({ points, theme }: { points: ScreenPoint[]; theme: Theme }) {
  const start = points[0];
  // A short way along the curve, not a fixed index: on a 100-point solve that
  // is sample 4, and on a stubby array it is still the neighbour rather than
  // the far end, which would point the launch arrow along the chord instead of
  // the tangent.
  const next = points[Math.max(1, Math.round((points.length - 1) * 0.04))];
  const apex = points.reduce((best, p) => (p.py < best.py ? p : best), points[0]);

  const dx = next.px - start.px;
  const dy = next.py - start.py;
  const len = Math.hypot(dx, dy) || 1;

  return (
    <G testID="trajectory-arrows">
      <Arrow
        x1={start.px}
        y1={start.py}
        x2={start.px + (dx / len) * ARROW_LENGTH}
        y2={start.py + (dy / len) * ARROW_LENGTH}
        color={theme.primary}
      />
      <Arrow
        x1={apex.px}
        y1={apex.py}
        x2={apex.px}
        y2={apex.py + ARROW_LENGTH}
        color={theme.textSecondary}
      />
    </G>
  );
}

function Arrow({
  x1,
  y1,
  x2,
  y2,
  color,
}: {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  color: string;
}) {
  const dx = x2 - x1;
  const dy = y2 - y1;
  const len = Math.hypot(dx, dy) || 1;
  const ux = dx / len;
  const uy = dy / len;
  // Perpendicular, for the two base corners of the head.
  const head = `${x2},${y2} ${x2 - ux * ARROW_HEAD + uy * ARROW_HEAD * 0.6},${
    y2 - uy * ARROW_HEAD - ux * ARROW_HEAD * 0.6
  } ${x2 - ux * ARROW_HEAD - uy * ARROW_HEAD * 0.6},${
    y2 - uy * ARROW_HEAD + ux * ARROW_HEAD * 0.6
  }`;

  return (
    <G>
      <Line x1={x1} y1={y1} x2={x2} y2={y2} stroke={color} strokeWidth={1.5} />
      <Polygon points={head} fill={color} />
    </G>
  );
}

const localStyles = StyleSheet.create({
  playButton: {
    marginTop: 8,
    paddingVertical: 6,
    paddingHorizontal: 16,
    borderRadius: 16,
    borderWidth: StyleSheet.hairlineWidth,
  },
  playLabel: {
    fontSize: 13,
    fontWeight: "600",
  },
});
