/* eslint-disable react-hooks/immutability -- Reanimated shared values are mutated on the UI thread by design */
/**
 * The `simulation` fence: a scene of moving bodies, not a plot of one.
 *
 * P3 animated the trajectory *graph*, which shows the shape of the path. Seven
 * of the eleven verified physics kinds draw nothing at all, and for several the
 * picture is the explanation — an orbiting dot is the most natural animation in
 * the subject, and circular motion had no visual whatsoever.
 *
 * Built on `TrajectoryChart`'s pattern rather than beside it: one shared
 * `progress`, `useAnimatedProps` on SVG elements, play-not-autoplay, and a
 * Reduce Motion path. What is new is that this is a *scene* — one uniform scale
 * on both axes (an orbit drawn on stretched axes is an ellipse), a ground line
 * or a slope, and force arrows that point somewhere in the world rather than
 * along an axis.
 *
 * Seven scenes, in two families. Four have something moving — a projectile, an
 * orbit, a two-body collision, a block sliding down a slope — and three are
 * still figures: a see-saw, a free-body diagram, a sum of force vectors. The
 * still ones are not a lesser case; a free-body diagram is exactly what a force
 * question is asking to see, and a scene with nothing to play offers no Play.
 *
 * Most arrows are derived from the body's own sampled path, so they cannot
 * disagree with the motion they annotate. Two kinds cannot be: normal and
 * friction come off the stated slope, because a block that has not started
 * moving has no tangent; and `vectors` are stated outright, because the
 * direction of a resultant *is* the answer.
 *
 * As everywhere else in this pipeline, no physics is repeated on the device.
 */
import { useCallback, useEffect, useMemo } from "react";
import { Pressable, StyleSheet, Text, useWindowDimensions, View } from "react-native";
import { useTranslation } from "react-i18next";
import Svg, { Circle, G, Line, Polygon, Polyline, Text as SvgText } from "react-native-svg";
import Animated, {
  cancelAnimation,
  useAnimatedProps,
  useSharedValue,
  withTiming,
} from "react-native-reanimated";

import {
  arrowPolyline,
  inclineDirections,
  inclineSurface,
  parseSimulationSpec,
  polylinePoints,
  projectPath,
  simulationTransform,
  tangentAt,
  worldToScreen,
  type SimulationArrow,
  type SimulationSpec,
  type SimulationVector,
  type SimulationTransform,
  type ScreenPoint,
} from "@/lib/math/simulation";
import { trajectoryPointAt } from "@/lib/math/trajectory";
import { Motion, useReduceMotion } from "@/lib/motion";
import { Theme, useTheme } from "@/lib/theme";

const AnimatedCircle = Animated.createAnimatedComponent(Circle);
const AnimatedPolyline = Animated.createAnimatedComponent(Polyline);

export const SIMULATION_PAD = 24;
export const SIMULATION_HEIGHT = 240;

const ARROW_LENGTH = 38;
const ARROW_HEAD = 7;
const MIN_BODY_RADIUS = 4;
const PIVOT_SIZE = 7;
const LABEL_OFFSET = 8;

type Props = { content: string };

export function SimulationBlock({ content }: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const { width: screenWidth } = useWindowDimensions();
  const reduceMotion = useReduceMotion();
  const progress = useSharedValue(0);

  const spec = useMemo(() => parseSimulationSpec(content), [content]);
  const width = Math.min(screenWidth - 48, 360);
  const styles = useMemo(() => makeStyles(theme), [theme]);

  const transform = useMemo(
    () => (spec ? simulationTransform(spec, width, SIMULATION_HEIGHT, SIMULATION_PAD) : null),
    [spec, width],
  );
  // Screen coordinates, computed once per body. The worklets index these
  // arrays rather than mapping on every frame.
  const tracks = useMemo(
    () => (spec && transform ? spec.bodies.map((b) => projectPath(b.path, transform)) : []),
    [spec, transform],
  );

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

  if (!spec || !transform) {
    return (
      <View style={styles.fallback}>
        <Text style={styles.fallbackText}>{t("rich.simulation_error")}</Text>
      </View>
    );
  }

  const centre = spec.centre ? worldToScreen(spec.centre.x, spec.centre.y, transform) : null;
  const groundY = worldToScreen(0, 0, transform).py;
  const surface = inclineSurface(spec, transform);
  const slope = spec.inclineDeg !== undefined ? inclineDirections(spec.inclineDeg) : null;
  const beam = spec.beam
    ? {
        a: worldToScreen(spec.beam.x1, spec.beam.y1, transform),
        b: worldToScreen(spec.beam.x2, spec.beam.y2, transform),
      }
    : null;
  const pivot = spec.pivot ? worldToScreen(spec.pivot.x, spec.pivot.y, transform) : null;
  const statedVectors = spec.vectors;
  // A see-saw has nothing to play, and a button that does nothing when pressed
  // is worse than no button. Checked from the paths rather than the scene type
  // so a future still scene needs no second list to be added to.
  const animated = spec.bodies.some((body) =>
    body.path.some((point) => point[0] !== body.path[0][0] || point[1] !== body.path[0][1]),
  );

  return (
    <View style={styles.wrap}>
      <Text style={styles.title}>{spec.title ?? t("rich.simulation_title")}</Text>
      <Svg width={width} height={SIMULATION_HEIGHT}>
        {/* The route each body takes, drawn once and never dimmed. Playback is
            an addition to the scene, not a precondition for reading it — the
            same rule P3 settled on for the trajectory curve. For an orbit this
            faint ring is most of the diagram. */}
        {tracks.map((track, i) => (
          <Polyline
            key={`path-${i}`}
            points={polylinePoints(track)}
            fill="none"
            stroke={theme.border}
            strokeWidth={1.5}
            strokeDasharray={[4, 4]}
          />
        ))}
        {surface && (
          <Line
            testID="simulation-slope"
            x1={surface.x1}
            y1={surface.y1}
            x2={surface.x2}
            y2={surface.y2}
            stroke={theme.textSecondary}
            strokeWidth={1.5}
          />
        )}
        {spec.ground && (
          <Line
            testID="simulation-ground"
            x1={SIMULATION_PAD / 2}
            y1={groundY}
            x2={width - SIMULATION_PAD / 2}
            y2={groundY}
            stroke={theme.textSecondary}
            strokeWidth={1.5}
          />
        )}
        {beam && (
          <Line
            testID="simulation-beam"
            x1={beam.a.px}
            y1={beam.a.py}
            x2={beam.b.px}
            y2={beam.b.py}
            stroke={theme.textSecondary}
            strokeWidth={3}
            strokeLinecap="round"
          />
        )}
        {pivot && (
          // A wedge under the beam: the shape that says "this turns about
          // here" without a word of explanation.
          <Polygon
            testID="simulation-pivot"
            points={`${pivot.px},${pivot.py} ${pivot.px - PIVOT_SIZE},${pivot.py + PIVOT_SIZE * 1.4} ${pivot.px + PIVOT_SIZE},${pivot.py + PIVOT_SIZE * 1.4}`}
            fill={theme.textSecondary}
          />
        )}
        {statedVectors.map((vector, i) => (
          <StatedVector
            key={`vector-${i}`}
            vector={vector}
            transform={transform}
            theme={theme}
          />
        ))}
        {centre && (
          <Circle
            testID="simulation-centre"
            cx={centre.px}
            cy={centre.py}
            r={3}
            fill={theme.textSecondary}
          />
        )}
        {spec.bodies.map((body, i) => (
          <BodyMarks
            key={`body-${i}`}
            track={tracks[i]}
            radius={Math.max(body.radius * transform.scale, MIN_BODY_RADIUS)}
            role={body.role}
            arrows={spec.arrows}
            centre={centre}
            slope={slope}
            progress={progress}
            reduceMotion={reduceMotion}
            theme={theme}
          />
        ))}
      </Svg>
      {!reduceMotion && animated && (
        <Pressable
          testID="simulation-play"
          accessibilityRole="button"
          accessibilityLabel={t("rich.graph_play_a11y")}
          onPress={play}
          style={({ pressed }) => [
            styles.playButton,
            { borderColor: theme.border, opacity: pressed ? 0.6 : 1 },
          ]}
        >
          <Text style={[styles.playLabel, { color: theme.primary }]}>{t("rich.graph_play")}</Text>
        </Pressable>
      )}
    </View>
  );
}

type BodyMarksProps = {
  track: ScreenPoint[];
  radius: number;
  role: "primary" | "secondary";
  arrows: SimulationArrow[];
  centre: ScreenPoint | null;
  slope: { normal: Vector; friction: Vector } | null;
  progress: { value: number };
  reduceMotion: boolean;
  theme: Theme;
};

type Vector = { dx: number; dy: number };

/**
 * One body and the vectors hanging off it.
 *
 * Under Reduce Motion this is the whole point rather than a degraded version
 * of it: body and arrows are drawn statically at the first sample, which is
 * the free-body diagram at launch — a real still picture, not an empty box.
 */
function BodyMarks({
  track,
  radius,
  role,
  arrows,
  centre,
  slope,
  progress,
  reduceMotion,
  theme,
}: BodyMarksProps) {
  const color = role === "primary" ? theme.primary : theme.textSecondary;

  const bodyProps = useAnimatedProps(() => {
    const at = trajectoryPointAt(track, progress.value);
    return { cx: at.px, cy: at.py };
  });

  // Each arrow is its own animated polyline so a scene can show more than one
  // without them sharing a worklet and having to be rebuilt together.
  const gravityProps = useAnimatedProps(() => {
    const at = trajectoryPointAt(track, progress.value);
    return { points: arrowPolyline(at, 0, 1, ARROW_LENGTH, ARROW_HEAD) };
  });
  const velocityProps = useAnimatedProps(() => {
    const at = trajectoryPointAt(track, progress.value);
    const tangent = tangentAt(track, progress.value);
    return { points: arrowPolyline(at, tangent.dx, tangent.dy, ARROW_LENGTH, ARROW_HEAD) };
  });
  const centripetalProps = useAnimatedProps(() => {
    const at = trajectoryPointAt(track, progress.value);
    if (!centre) return { points: "" };
    return {
      points: arrowPolyline(at, centre.px - at.px, centre.py - at.py, ARROW_LENGTH, ARROW_HEAD),
    };
  });
  // Both directions are fixed by the slope, so they do not change with the
  // frame — but they still ride the body, which does.
  const normalProps = useAnimatedProps(() => {
    const at = trajectoryPointAt(track, progress.value);
    if (!slope) return { points: "" };
    return {
      points: arrowPolyline(at, slope.normal.dx, slope.normal.dy, ARROW_LENGTH, ARROW_HEAD),
    };
  });
  const frictionProps = useAnimatedProps(() => {
    const at = trajectoryPointAt(track, progress.value);
    if (!slope) return { points: "" };
    return {
      points: arrowPolyline(at, slope.friction.dx, slope.friction.dy, ARROW_LENGTH, ARROW_HEAD),
    };
  });

  if (reduceMotion) {
    return (
      <StaticBodyMarks
        track={track}
        radius={radius}
        arrows={arrows}
        centre={centre}
        slope={slope}
        color={color}
        theme={theme}
      />
    );
  }

  return (
    <G>
      {arrows.includes("gravity") && (
        <AnimatedPolyline
          testID="simulation-arrow-gravity"
          fill="none"
          stroke={theme.textSecondary}
          strokeWidth={1.5}
          animatedProps={gravityProps}
        />
      )}
      {arrows.includes("velocity") && (
        <AnimatedPolyline
          testID="simulation-arrow-velocity"
          fill="none"
          stroke={color}
          strokeWidth={1.5}
          animatedProps={velocityProps}
        />
      )}
      {centre && arrows.includes("centripetal") && (
        <AnimatedPolyline
          testID="simulation-arrow-centripetal"
          fill="none"
          stroke={theme.textSecondary}
          strokeWidth={1.5}
          animatedProps={centripetalProps}
        />
      )}
      {slope && arrows.includes("normal") && (
        <AnimatedPolyline
          testID="simulation-arrow-normal"
          fill="none"
          stroke={theme.textSecondary}
          strokeWidth={1.5}
          animatedProps={normalProps}
        />
      )}
      {slope && arrows.includes("friction") && (
        <AnimatedPolyline
          testID="simulation-arrow-friction"
          fill="none"
          stroke={theme.textSecondary}
          strokeWidth={1.5}
          animatedProps={frictionProps}
        />
      )}
      <AnimatedCircle
        testID="simulation-body"
        r={radius}
        fill={color}
        stroke={theme.bg}
        strokeWidth={1.5}
        animatedProps={bodyProps}
      />
    </G>
  );
}

/** The same marks at the first sample, with nothing moving. */
function StaticBodyMarks({
  track,
  radius,
  arrows,
  centre,
  slope,
  color,
  theme,
}: {
  track: ScreenPoint[];
  radius: number;
  arrows: SimulationArrow[];
  centre: ScreenPoint | null;
  slope: { normal: Vector; friction: Vector } | null;
  color: string;
  theme: Theme;
}) {
  const at = track[0];
  const tangent = tangentAt(track, 0);

  return (
    <G testID="simulation-static">
      {arrows.includes("gravity") && (
        <Polyline
          testID="simulation-arrow-gravity"
          points={arrowPolyline(at, 0, 1, ARROW_LENGTH, ARROW_HEAD)}
          fill="none"
          stroke={theme.textSecondary}
          strokeWidth={1.5}
        />
      )}
      {arrows.includes("velocity") && (
        <Polyline
          testID="simulation-arrow-velocity"
          points={arrowPolyline(at, tangent.dx, tangent.dy, ARROW_LENGTH, ARROW_HEAD)}
          fill="none"
          stroke={color}
          strokeWidth={1.5}
        />
      )}
      {centre && arrows.includes("centripetal") && (
        <Polyline
          testID="simulation-arrow-centripetal"
          points={arrowPolyline(at, centre.px - at.px, centre.py - at.py, ARROW_LENGTH, ARROW_HEAD)}
          fill="none"
          stroke={theme.textSecondary}
          strokeWidth={1.5}
        />
      )}
      {slope && arrows.includes("normal") && (
        <Polyline
          testID="simulation-arrow-normal"
          points={arrowPolyline(at, slope.normal.dx, slope.normal.dy, ARROW_LENGTH, ARROW_HEAD)}
          fill="none"
          stroke={theme.textSecondary}
          strokeWidth={1.5}
        />
      )}
      {slope && arrows.includes("friction") && (
        <Polyline
          testID="simulation-arrow-friction"
          points={arrowPolyline(at, slope.friction.dx, slope.friction.dy, ARROW_LENGTH, ARROW_HEAD)}
          fill="none"
          stroke={theme.textSecondary}
          strokeWidth={1.5}
        />
      )}
      <Circle
        testID="simulation-body"
        cx={at.px}
        cy={at.py}
        r={radius}
        fill={color}
        stroke={theme.bg}
        strokeWidth={1.5}
      />
    </G>
  );
}

/**
 * One arrow the solver stated, with its label at the tip.
 *
 * Nothing here animates: these are the forces on a still figure, and a
 * see-saw whose loads drifted would be describing a different problem.
 *
 * On a `vector_sum` the length carries meaning — the resultant must visibly
 * out-reach its components or the picture contradicts its own answer — so the
 * world length is used where the scene gives one. Everywhere else the
 * magnitudes live in the labels and the arrows are drawn at one size, because
 * a 59 N tension against a 49 N weight would differ by a fifth of an arrowhead.
 */
function StatedVector({
  vector,
  transform,
  theme,
}: {
  vector: SimulationVector;
  transform: SimulationTransform;
  theme: Theme;
}) {
  const from = worldToScreen(vector.anchor.x, vector.anchor.y, transform);
  const worldLength = Math.hypot(vector.dx, vector.dy);
  // A unit-ish direction means "no length stated" — draw the standard arrow.
  // A measure is the exception in the other direction: its length *is* the
  // quantity, so it spans exactly what it says even when that is short.
  const scaled = worldLength * transform.scale;
  const length =
    vector.role === "measure" || scaled > ARROW_LENGTH * 1.2 ? scaled : ARROW_LENGTH;
  // World y is up, screen y is down.
  const points = arrowPolyline(from, vector.dx, -vector.dy, length, ARROW_HEAD);
  if (!points) return null;

  const measure = vector.role === "measure";
  const color = vector.role === "result" ? theme.primary : theme.textSecondary;
  const tipX = from.px + (vector.dx / (worldLength || 1)) * length;
  const tipY = from.py - (vector.dy / (worldLength || 1)) * length;

  return (
    // The label is on the group as well as drawn, so a screen reader announces
    // "T = 59.05 N" rather than silence — an SVG <Text> is not a text node a
    // reader (or a test) can reach.
    <G
      testID={`simulation-vector-${vector.role}`}
      accessible={vector.label !== undefined}
      accessibilityLabel={vector.label}
    >
      <Polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth={vector.role === "result" ? 2.5 : 1.5}
        // Dashed so a height or a distance does not read as a third force
        // acting on the block.
        strokeDasharray={measure ? [3, 3] : undefined}
      />
      {vector.label && (
        <SvgText
          testID="simulation-vector-label"
          x={tipX + (vector.dx >= 0 ? LABEL_OFFSET : -LABEL_OFFSET)}
          y={tipY + (vector.dy > 0 ? -LABEL_OFFSET : LABEL_OFFSET * 1.6)}
          fill={color}
          fontSize={11}
          textAnchor={vector.dx >= 0 ? "start" : "end"}
        >
          {vector.label}
        </SvgText>
      )}
    </G>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    wrap: {
      marginVertical: 8,
      alignItems: "center",
    },
    title: {
      fontSize: 13,
      fontWeight: "600",
      color: theme.textSecondary,
      marginBottom: 6,
    },
    fallback: {
      marginVertical: 8,
      padding: 12,
      borderRadius: 12,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
    },
    fallbackText: {
      fontSize: 13,
      color: theme.textSecondary,
    },
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
}

export type { SimulationSpec, SimulationTransform };
