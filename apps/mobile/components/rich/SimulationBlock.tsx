/* eslint-disable react-hooks/immutability -- Reanimated shared values are mutated on the UI thread by design */
/** Native Skia renderer for verified physics simulation scenes. */
import { useCallback, useEffect, useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, useWindowDimensions, View } from "react-native";
import { useTranslation } from "react-i18next";
import {
  Canvas,
  Circle,
  DashPathEffect,
  Path,
  Skia,
  Text as SkiaText,
  useFont,
  type SkFont,
} from "@shopify/react-native-skia";
import {
  cancelAnimation,
  runOnJS,
  useDerivedValue,
  useSharedValue,
  withTiming,
  type SharedValue,
} from "react-native-reanimated";

import {
  clampCanvasLabelBaseline,
  clampCanvasLabelX,
  inclineDirections,
  inclineSurface,
  parseSimulationSpec,
  projectPath,
  simulationTransform,
  simulationViewportHeight,
  tangentAt,
  worldToScreen,
  type SimulationArrow,
  type SimulationSpec,
  type SimulationTransform,
  type SimulationVector,
  type ScreenPoint,
} from "@/lib/math/simulation";
import {
  playbackStart,
  remainingPlaybackDuration,
} from "@/lib/animationPlayback";
import { Icon } from "@/ui/icons/Icon";
import { trajectoryPointAt } from "@/lib/math/trajectory";
import { Motion, useReduceMotion } from "@/lib/motion";
import { Theme, useTheme } from "@/lib/theme";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";

export const SIMULATION_PAD = 24;
export const SIMULATION_HEIGHT = 240;
export const SIMULATION_MIN_HEIGHT = 136;

const ARROW_LENGTH = 38;
const ARROW_HEAD = 7;
const MIN_BODY_RADIUS = 4;
const PIVOT_SIZE = 7;
const LABEL_OFFSET = 8;
const LABEL_FONT_SIZE = 11;

type Props = { content: string };
type Vector = { dx: number; dy: number };

function pointsPath(points: readonly ScreenPoint[]) {
  const path = Skia.Path.Make();
  points.forEach((point, index) => {
    if (index === 0) path.moveTo(point.px, point.py);
    else path.lineTo(point.px, point.py);
  });
  return path;
}

function linePath(x1: number, y1: number, x2: number, y2: number) {
  const path = Skia.Path.Make();
  path.moveTo(x1, y1);
  path.lineTo(x2, y2);
  return path;
}

function arrowPath(
  from: ScreenPoint,
  dx: number,
  dy: number,
  length: number,
  head: number,
) {
  "worklet";
  const path = Skia.Path.Make();
  const magnitude = Math.hypot(dx, dy);
  if (magnitude === 0) return path;
  const ux = dx / magnitude;
  const uy = dy / magnitude;
  const tipX = from.px + ux * length;
  const tipY = from.py + uy * length;
  const bx = uy * head * 0.6;
  const by = ux * head * 0.6;
  path.moveTo(from.px, from.py);
  path.lineTo(tipX, tipY);
  path.moveTo(tipX, tipY);
  path.lineTo(tipX - ux * head + bx, tipY - uy * head - by);
  path.moveTo(tipX, tipY);
  path.lineTo(tipX - ux * head - bx, tipY - uy * head + by);
  return path;
}

function pivotPath(point: ScreenPoint) {
  const path = Skia.Path.Make();
  path.moveTo(point.px, point.py);
  path.lineTo(point.px - PIVOT_SIZE, point.py + PIVOT_SIZE * 1.4);
  path.lineTo(point.px + PIVOT_SIZE, point.py + PIVOT_SIZE * 1.4);
  path.close();
  return path;
}

export function SimulationBlock({ content }: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const { width: screenWidth } = useWindowDimensions();
  const reduceMotion = useReduceMotion();
  const progress = useSharedValue(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const font = useFont(require("../../assets/fonts/SpaceMono-Regular.ttf"), LABEL_FONT_SIZE);
  const spec = useMemo(() => parseSimulationSpec(content), [content]);
  const width = Math.min(screenWidth - 48, 360);
  const styles = useMemo(() => makeStyles(theme), [theme]);
  const height = useMemo(
    () =>
      spec
        ? simulationViewportHeight(
            spec,
            width,
            SIMULATION_PAD,
            SIMULATION_MIN_HEIGHT,
            SIMULATION_HEIGHT,
          )
        : SIMULATION_HEIGHT,
    [spec, width],
  );
  const transform = useMemo(
    () => (spec ? simulationTransform(spec, width, height, SIMULATION_PAD) : null),
    [height, spec, width],
  );
  const tracks = useMemo(
    () => (spec && transform ? spec.bodies.map((body) => projectPath(body.path, transform)) : []),
    [spec, transform],
  );
  const trackPaths = useMemo(() => tracks.map(pointsPath), [tracks]);
  const animated = useMemo(
    () =>
      spec?.bodies.some((body) =>
        body.path.some(
          (point) => point[0] !== body.path[0][0] || point[1] !== body.path[0][1],
        ),
      ) ?? false,
    [spec],
  );
  const compactTitleTop = useMemo(() => {
    if (!spec || !transform || !animated || height >= SIMULATION_HEIGHT) return null;
    const bodyTop = tracks.reduce((sceneTop, track, index) => {
      const radius = Math.max(
        spec.bodies[index].radius * transform.scale,
        MIN_BODY_RADIUS,
      );
      const trackTop = track.reduce(
        (top, point) => Math.min(top, point.py - radius),
        Number.POSITIVE_INFINITY,
      );
      return Math.min(sceneTop, trackTop);
    }, Number.POSITIVE_INFINITY);
    if (!Number.isFinite(bodyTop)) return null;
    return Math.max(4, bodyTop - 24);
  }, [animated, height, spec, tracks, transform]);

  const markStopped = useCallback(() => setIsPlaying(false), []);
  const play = useCallback(() => {
    cancelAnimation(progress);
    const start = playbackStart(progress.value);
    progress.value = start;
    setIsPlaying(true);
    progress.value = withTiming(
      1,
      {
        duration: remainingPlaybackDuration(Motion.duration.simulation, start),
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
    if (!animated || reduceMotion) return;
    play();
    return () => cancelAnimation(progress);
  }, [animated, play, progress, reduceMotion]);

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

  return (
    <View style={styles.wrap}>
      {compactTitleTop === null ? (
        <Text style={styles.title}>{spec.title ?? t("rich.simulation_title")}</Text>
      ) : null}
      <View style={{ width, height }}>
        <Canvas
          testID="simulation-canvas"
          style={{ width, height }}
        >
          {trackPaths.map((path, index) => (
            <Path
              key={`track-${index}`}
              path={path}
              color={theme.border}
              style="stroke"
              strokeWidth={1.5}
            >
              <DashPathEffect intervals={[4, 4]} />
            </Path>
          ))}
          {surface ? (
            <Path
              path={linePath(surface.x1, surface.y1, surface.x2, surface.y2)}
              color={theme.textSecondary}
              style="stroke"
              strokeWidth={1.5}
            />
          ) : null}
          {spec.ground ? (
            <Path
              path={linePath(SIMULATION_PAD / 2, groundY, width - SIMULATION_PAD / 2, groundY)}
              color={theme.textSecondary}
              style="stroke"
              strokeWidth={1.5}
            />
          ) : null}
          {beam ? (
            <Path
              path={linePath(beam.a.px, beam.a.py, beam.b.px, beam.b.py)}
              color={theme.textSecondary}
              style="stroke"
              strokeWidth={3}
              strokeCap="round"
            />
          ) : null}
          {pivot ? <Path path={pivotPath(pivot)} color={theme.textSecondary} /> : null}
          {spec.vectors.map((vector, index) => (
            <StatedVector
              key={`vector-${index}`}
              vector={vector}
              transform={transform}
              theme={theme}
              font={font}
              canvasWidth={width}
              canvasHeight={height}
            />
          ))}
          {centre ? <Circle cx={centre.px} cy={centre.py} r={3} color={theme.textSecondary} /> : null}
          {spec.bodies.map((body, index) => (
            <BodyMarks
              key={`body-${index}`}
              track={tracks[index]}
              radius={Math.max(body.radius * transform.scale, MIN_BODY_RADIUS)}
              label={body.label}
              role={body.role}
              arrows={spec.arrows}
              centre={centre}
              slope={slope}
              progress={progress}
              theme={theme}
              font={font}
              canvasWidth={width}
              canvasHeight={height}
            />
          ))}
        </Canvas>
        {compactTitleTop !== null ? (
          <Text
            pointerEvents="none"
            style={[styles.title, styles.titleOverlay, { top: compactTitleTop, width }]}
          >
            {spec.title ?? t("rich.simulation_title")}
          </Text>
        ) : null}
        <SceneMarkers
          spec={spec}
          surface={surface !== null}
          centre={centre !== null}
          beam={beam !== null}
          pivot={pivot !== null}
          reduceMotion={reduceMotion}
        />
      </View>
      {!reduceMotion && animated ? (
        <Pressable
          testID="simulation-control"
          accessibilityRole="button"
          accessibilityLabel={t(
            isPlaying ? "rich.simulation_pause_a11y" : "rich.simulation_play_a11y",
          )}
          onPress={isPlaying ? pause : play}
          style={({ pressed }) => [
            styles.control,
            { borderColor: theme.border, opacity: pressed ? 0.6 : 1 },
          ]}
        >
          <Icon
            testID={isPlaying ? "simulation-stop-symbol" : "simulation-play-symbol"}
            name={isPlaying ? "pause" : "play"}
            size={20}
            color={theme.primary}
          />
        </Pressable>
      ) : null}
    </View>
  );
}

function BodyMarks({
  track,
  radius,
  label,
  role,
  arrows,
  centre,
  slope,
  progress,
  theme,
  font,
  canvasWidth,
  canvasHeight,
}: {
  track: ScreenPoint[];
  radius: number;
  label?: string;
  role: "primary" | "secondary";
  arrows: SimulationArrow[];
  centre: ScreenPoint | null;
  slope: { normal: Vector; friction: Vector } | null;
  progress: SharedValue<number>;
  theme: Theme;
  font: SkFont | null;
  canvasWidth: number;
  canvasHeight: number;
}) {
  const color = role === "primary" ? theme.primary : theme.textSecondary;
  const at = useDerivedValue(() => trajectoryPointAt(track, progress.value));
  const bodyX = useDerivedValue(() => at.value.px);
  const bodyY = useDerivedValue(() => at.value.py);
  const labelWidth = label && font ? font.measureText(label).width : 0;
  const labelX = useDerivedValue(() => {
    const left = at.value.px - radius - LABEL_OFFSET - labelWidth;
    const preferred = left >= 4 ? left : at.value.px + radius + LABEL_OFFSET;
    return clampCanvasLabelX(preferred, labelWidth, canvasWidth);
  });
  const labelY = useDerivedValue(() =>
    clampCanvasLabelBaseline(at.value.py + 4, LABEL_FONT_SIZE, canvasHeight),
  );
  const gravity = useDerivedValue(() =>
    arrowPath(at.value, 0, 1, ARROW_LENGTH, ARROW_HEAD),
  );
  const velocity = useDerivedValue(() => {
    const tangent = tangentAt(track, progress.value);
    return arrowPath(at.value, tangent.dx, tangent.dy, ARROW_LENGTH, ARROW_HEAD);
  });
  const centripetal = useDerivedValue(() =>
    centre
      ? arrowPath(
          at.value,
          centre.px - at.value.px,
          centre.py - at.value.py,
          ARROW_LENGTH,
          ARROW_HEAD,
        )
      : Skia.Path.Make(),
  );
  const normal = useDerivedValue(() =>
    slope
      ? arrowPath(at.value, slope.normal.dx, slope.normal.dy, ARROW_LENGTH, ARROW_HEAD)
      : Skia.Path.Make(),
  );
  const friction = useDerivedValue(() =>
    slope
      ? arrowPath(at.value, slope.friction.dx, slope.friction.dy, ARROW_LENGTH, ARROW_HEAD)
      : Skia.Path.Make(),
  );

  return (
    <>
      {arrows.includes("gravity") ? (
        <Path path={gravity} color={theme.textSecondary} style="stroke" strokeWidth={1.5} />
      ) : null}
      {arrows.includes("velocity") ? (
        <Path path={velocity} color={color} style="stroke" strokeWidth={1.5} />
      ) : null}
      {centre && arrows.includes("centripetal") ? (
        <Path path={centripetal} color={theme.textSecondary} style="stroke" strokeWidth={1.5} />
      ) : null}
      {slope && arrows.includes("normal") ? (
        <Path path={normal} color={theme.textSecondary} style="stroke" strokeWidth={1.5} />
      ) : null}
      {slope && arrows.includes("friction") ? (
        <Path path={friction} color={theme.textSecondary} style="stroke" strokeWidth={1.5} />
      ) : null}
      <Circle cx={bodyX} cy={bodyY} r={radius + 1.5} color={theme.bg} />
      <Circle cx={bodyX} cy={bodyY} r={radius} color={color} />
      {label && font ? (
        <SkiaText
          x={labelX}
          y={labelY}
          text={label}
          font={font}
          color={theme.textSecondary}
        />
      ) : null}
    </>
  );
}

function StatedVector({
  vector,
  transform,
  theme,
  font,
  canvasWidth,
  canvasHeight,
}: {
  vector: SimulationVector;
  transform: SimulationTransform;
  theme: Theme;
  font: SkFont | null;
  canvasWidth: number;
  canvasHeight: number;
}) {
  const from = worldToScreen(vector.anchor.x, vector.anchor.y, transform);
  const worldLength = Math.hypot(vector.dx, vector.dy);
  const scaled = worldLength * transform.scale;
  const length = vector.role === "measure" || scaled > ARROW_LENGTH * 1.2 ? scaled : ARROW_LENGTH;
  const path = arrowPath(from, vector.dx, -vector.dy, length, ARROW_HEAD);
  const color = vector.role === "result" ? theme.primary : theme.textSecondary;
  const tipX = from.px + (vector.dx / (worldLength || 1)) * length;
  const tipY = from.py - (vector.dy / (worldLength || 1)) * length;
  const labelWidth = vector.label && font ? font.measureText(vector.label).width : 0;
  const textX = clampCanvasLabelX(
    tipX + (vector.dx >= 0 ? LABEL_OFFSET : -LABEL_OFFSET - labelWidth),
    labelWidth,
    canvasWidth,
  );
  const textY = clampCanvasLabelBaseline(
    tipY + (vector.dy > 0 ? -LABEL_OFFSET : LABEL_OFFSET * 1.6),
    LABEL_FONT_SIZE,
    canvasHeight,
  );

  return (
    <>
      <Path
        path={path}
        color={color}
        style="stroke"
        strokeWidth={vector.role === "result" ? 2.5 : 1.5}
      >
        {vector.role === "measure" ? <DashPathEffect intervals={[3, 3]} /> : null}
      </Path>
      {vector.label && font ? (
        <SkiaText
          x={textX}
          y={textY}
          text={vector.label}
          font={font}
          color={color}
        />
      ) : null}
    </>
  );
}

function SceneMarkers({
  spec,
  surface,
  centre,
  beam,
  pivot,
  reduceMotion,
}: {
  spec: SimulationSpec;
  surface: boolean;
  centre: boolean;
  beam: boolean;
  pivot: boolean;
  reduceMotion: boolean;
}) {
  return (
    <View pointerEvents="none" style={StyleSheet.absoluteFill}>
      {surface ? <View testID="simulation-slope" style={markerStyle} /> : null}
      {spec.ground ? <View testID="simulation-ground" style={markerStyle} /> : null}
      {beam ? <View testID="simulation-beam" style={markerStyle} /> : null}
      {pivot ? <View testID="simulation-pivot" style={markerStyle} /> : null}
      {centre ? <View testID="simulation-centre" style={markerStyle} /> : null}
      {reduceMotion ? <View testID="simulation-static" style={markerStyle} /> : null}
      {spec.bodies.map((body, bodyIndex) => (
        <View key={`body-marker-${bodyIndex}`}>
          <View
            testID="simulation-body"
            accessible={body.label !== undefined}
            accessibilityLabel={body.label}
            style={markerStyle}
          />
          {body.label ? <View testID="simulation-body-label" style={markerStyle} /> : null}
          {spec.arrows.map((arrow) => (
            <View
              key={`${bodyIndex}-${arrow}`}
              testID={`simulation-arrow-${arrow}`}
              style={markerStyle}
            />
          ))}
        </View>
      ))}
      {spec.vectors.map((vector, index) => (
        <View
          key={`vector-marker-${index}`}
          testID={`simulation-vector-${vector.role}`}
          accessible={vector.label !== undefined}
          accessibilityLabel={vector.label}
          style={markerStyle}
        >
          {vector.label ? <View testID="simulation-vector-label" style={markerStyle} /> : null}
        </View>
      ))}
    </View>
  );
}

const markerStyle = {
  position: "absolute" as const,
  width: 1,
  height: 1,
  opacity: 0,
};

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    wrap: {
      marginVertical: Space.xs,
      alignItems: "center",
    },
    title: {
      fontSize: 13,
      fontWeight: "600",
      color: theme.textSecondary,
      marginBottom: 2,
      textAlign: "center",
    },
    titleOverlay: {
      position: "absolute",
      left: 0,
      zIndex: 1,
    },
    fallback: {
      marginVertical: Space.xs,
      padding: Space.sm,
      borderRadius: Radius.md,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
    },
    fallbackText: {
      fontSize: 13,
      color: theme.textSecondary,
    },
    control: {
      marginTop: Space.xs,
      width: 36,
      height: 36,
      alignItems: "center",
      justifyContent: "center",
      borderRadius: Radius.bubble,
      borderWidth: StyleSheet.hairlineWidth,
    },
  });
}

export type { SimulationSpec, SimulationTransform };
