/** Native Skia renderer for verified physics simulation scenes. */
import { useCallback, useMemo } from "react";
import { StyleSheet, Text, useWindowDimensions, View } from "react-native";
import { useTranslation } from "react-i18next";
import {
  Canvas,
  Circle,
  DashPathEffect,
  Path,
  Skia,
  useFont,
  type SkFont,
} from "@shopify/react-native-skia";
import { useDerivedValue, type SharedValue } from "react-native-reanimated";

import {
  arrowHeadSize,
  clampCanvasLabelBaseline,
  clampCanvasLabelX,
  derivedArrowGeometry,
  describeSimulation,
  inclineDirections,
  inclineSurface,
  isClosedPath,
  layoutSimulationScene,
  maxTrackSpeed,
  parseSimulationSpec,
  PIVOT_SIZE,
  projectPath,
  SIMULATION_HEIGHT,
  SIMULATION_MIN_HEIGHT,
  SIMULATION_PAD,
  simulationIsAnimated,
  simulationTransform,
  simulationViewportHeight,
  tangentAt,
  vectorStroke,
  worldToScreen,
  type BodyLabelLayout,
  type SimulationArrow,
  type SimulationSpec,
  type SimulationTransform,
  type ScreenPoint,
  type VectorLayout,
} from "@/lib/physics/simulation";
import { trajectoryPointAt } from "@/lib/math/trajectory";
import { Motion } from "@/lib/motion";
import { Theme, useTheme } from "@/lib/theme";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Type } from "@/lib/type";
import { figureTitleStyle, figureWidth } from "@/components/rich/figure";
import { PlaybackButton } from "@/components/rich/PlaybackButton";
import { usePlayback } from "@/components/rich/usePlayback";
import { HaloText } from "@/components/rich/skia/HaloText";
import {
  arrowHeadPath,
  arrowPath,
  arrowShaftPath,
  linePath,
  pointsPath,
} from "@/components/rich/skia/paths";

export { SIMULATION_HEIGHT, SIMULATION_MIN_HEIGHT, SIMULATION_PAD };

const LABEL_FONT_SIZE = 11;
/** Until the font loads, a rough SpaceMono advance keeps the layout sane. */
const FALLBACK_CHAR_WIDTH = 6.7;
const WALL_HALF_HEIGHT = 16;
const CENTRE_DOT_RADIUS = 3;
const ARROW_STROKE = 1.5;
const RESULT_STROKE = 2.5;

/** Periodic motion goes round again while playing; the rest hold their end. */
const PERIODIC: readonly SimulationSpec["type"][] = ["orbit", "spring"];

/**
 * The invisible geometry markers exist for component tests, which cannot see
 * inside a Skia canvas. They are never shipped to a screen reader.
 */
const RENDER_TEST_MARKERS = process.env.NODE_ENV === "test";

type Props = { content: string };
type Slope = ReturnType<typeof inclineDirections>;

function wallPath(point: ScreenPoint, floorY: number | null) {
  const path = Skia.Path.Make();
  path.moveTo(point.px, point.py - WALL_HALF_HEIGHT);
  // A wall standing on the ground stops at it rather than poking through.
  const bottom = point.py + WALL_HALF_HEIGHT;
  path.lineTo(point.px, floorY === null ? bottom : Math.min(bottom, floorY));
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

const COIL_COUNT = 8;
const COIL_WIDTH = 8;

function springPath(from: ScreenPoint, to: ScreenPoint) {
  "worklet";
  const path = Skia.Path.Make();
  const dx = to.px - from.px;
  const dy = to.py - from.py;
  const length = Math.hypot(dx, dy);
  path.moveTo(from.px, from.py);
  if (length < 1) {
    path.lineTo(to.px, to.py);
    return path;
  }
  const ux = dx / length;
  const uy = dy / length;
  const px = -uy;
  const py = ux;
  const turns = COIL_COUNT * 2;
  for (let i = 1; i < turns; i += 1) {
    const along = (i / turns) * length;
    const side = i % 2 === 0 ? COIL_WIDTH : -COIL_WIDTH;
    path.lineTo(from.px + ux * along + px * side, from.py + uy * along + py * side);
  }
  path.lineTo(to.px, to.py);
  return path;
}

export function SimulationBlock({ content }: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const { width: screenWidth } = useWindowDimensions();
  const font = useFont(require("../../assets/fonts/SpaceMono-Regular.ttf"), LABEL_FONT_SIZE);
  const spec = useMemo(() => parseSimulationSpec(content), [content]);
  const width = figureWidth(screenWidth);
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
  const closed = useMemo(() => tracks.map(isClosedPath), [tracks]);
  // One scale for every body, so the faster ball after a collision has the
  // longer arrow.
  const maxSpeed = useMemo(
    () =>
      spec?.arrows.includes("velocity")
        ? tracks.reduce((best, track, index) => Math.max(best, maxTrackSpeed(track, closed[index])), 0)
        : 0,
    [closed, spec, tracks],
  );
  // A spring's coil already runs along its path, so a trail would only
  // stripe the coil.
  const trackPaths = useMemo(
    () => (spec?.type === "spring" ? [] : tracks.map(pointsPath)),
    [spec, tracks],
  );
  const animated = useMemo(() => (spec ? simulationIsAnimated(spec) : false), [spec]);
  const measure = useCallback(
    (text: string) => (font ? font.measureText(text).width : text.length * FALLBACK_CHAR_WIDTH),
    [font],
  );
  const layout = useMemo(
    () =>
      spec && transform
        ? layoutSimulationScene(spec, transform, width, height, measure, LABEL_FONT_SIZE)
        : null,
    [height, measure, spec, transform, width],
  );
  const description = useMemo(() => (spec ? describeSimulation(spec, t) : ""), [spec, t]);
  const { progress, isPlaying, play, pause, reduceMotion } = usePlayback({
    duration: Motion.duration.simulation,
    animated,
    autoplay: true,
    loop: spec !== null && PERIODIC.includes(spec.type),
    resetKey: content,
  });

  if (!spec || !transform || !layout) {
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
  const anchor =
    spec.type === "spring" && spec.anchor
      ? worldToScreen(spec.anchor.x, spec.anchor.y, transform)
      : null;
  const bodyColor = (role: "primary" | "secondary") =>
    role === "primary" ? theme.primary : theme.graphSeries[1];

  return (
    <View style={styles.wrap}>
      <Text style={styles.title}>{spec.title ?? t("rich.simulation_title")}</Text>
      <View
        accessible
        accessibilityRole="image"
        accessibilityLabel={description}
        style={{ width, height }}
      >
        <Canvas testID="simulation-canvas" style={{ width, height }}>
          {trackPaths.map((path, index) => (
            <Path
              key={`track-${index}`}
              path={path}
              color={theme.textTertiary}
              style="stroke"
              strokeWidth={ARROW_STROKE}
            >
              <DashPathEffect intervals={[4, 4]} />
            </Path>
          ))}
          {surface ? (
            <Path
              path={linePath(surface.x1, surface.y1, surface.x2, surface.y2)}
              color={theme.textSecondary}
              style="stroke"
              strokeWidth={ARROW_STROKE}
            />
          ) : null}
          {spec.ground ? (
            <Path
              path={linePath(SIMULATION_PAD / 2, groundY, width - SIMULATION_PAD / 2, groundY)}
              color={theme.textSecondary}
              style="stroke"
              strokeWidth={ARROW_STROKE}
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
          {anchor ? (
            <Path
              path={wallPath(anchor, spec.ground ? groundY : null)}
              color={theme.textSecondary}
              style="stroke"
              strokeWidth={2}
            />
          ) : null}
          {anchor && tracks[0] ? (
            <SpringCoil
              anchor={anchor}
              track={tracks[0]}
              progress={progress}
              color={theme.textSecondary}
            />
          ) : null}
          {layout.vectors.map((vector, index) => (
            <StatedVector key={`vector-${index}`} layout={vector} theme={theme} />
          ))}
          {centre ? (
            <Circle cx={centre.px} cy={centre.py} r={CENTRE_DOT_RADIUS} color={theme.textSecondary} />
          ) : null}
          {spec.bodies.map((body, index) => (
            <BodyMarks
              key={`body-${index}`}
              track={tracks[index]}
              closed={closed[index]}
              maxSpeed={maxSpeed}
              radius={layout.radii[index]}
              color={bodyColor(body.role)}
              arrows={spec.arrows}
              centre={centre}
              slope={slope}
              progress={progress}
              theme={theme}
              canvasWidth={width}
              canvasHeight={height}
            />
          ))}
          {/* Labels last, over every line, each with a halo so nothing strikes it through. */}
          {font
            ? layout.vectors.map((vector, index) =>
                vector.label ? (
                  <HaloText
                    key={`vector-label-${index}`}
                    x={vector.label.x}
                    y={vector.label.y}
                    text={vector.label.text}
                    font={font}
                    color={vectorColor(vector, theme)}
                    halo={theme.bg}
                  />
                ) : null,
              )
            : null}
          {font
            ? spec.bodies.map((body, index) => {
                const label = layout.bodyLabels[index];
                return body.label && label ? (
                  <BodyLabel
                    key={`body-label-${index}`}
                    text={body.label}
                    layout={label}
                    track={tracks[index]}
                    progress={progress}
                    font={font}
                    theme={theme}
                    canvasWidth={width}
                    canvasHeight={height}
                  />
                ) : null;
              })
            : null}
        </Canvas>
        {RENDER_TEST_MARKERS ? (
          <SceneMarkers
            spec={spec}
            surface={surface !== null}
            centre={centre !== null}
            beam={beam !== null}
            pivot={pivot !== null}
            spring={anchor !== null}
            reduceMotion={reduceMotion === true}
          />
        ) : null}
      </View>
      {animated ? (
        <PlaybackButton
          testID="simulation"
          isPlaying={isPlaying}
          onPlay={play}
          onPause={pause}
          playLabel={t("rich.simulation_play_a11y")}
          pauseLabel={t("rich.simulation_pause_a11y")}
        />
      ) : null}
    </View>
  );
}

function vectorColor(vector: VectorLayout, theme: Theme): string {
  const role = vector.vector.role;
  // Motion shares the velocity arrow's colour family; the answer is primary.
  return role === "result" || role === "motion" ? theme.primary : theme.textSecondary;
}

function SpringCoil({
  anchor,
  track,
  progress,
  color,
}: {
  anchor: ScreenPoint;
  track: ScreenPoint[];
  progress: SharedValue<number>;
  color: string;
}) {
  const path = useDerivedValue(() =>
    springPath(anchor, trajectoryPointAt(track, progress.value)),
  );
  return <Path path={path} color={color} style="stroke" strokeWidth={ARROW_STROKE} />;
}

function BodyMarks({
  track,
  closed,
  maxSpeed,
  radius,
  color,
  arrows,
  centre,
  slope,
  progress,
  theme,
  canvasWidth,
  canvasHeight,
}: {
  track: ScreenPoint[];
  closed: boolean;
  maxSpeed: number;
  radius: number;
  color: string;
  arrows: SimulationArrow[];
  centre: ScreenPoint | null;
  slope: Slope | null;
  progress: SharedValue<number>;
  theme: Theme;
  canvasWidth: number;
  canvasHeight: number;
}) {
  const at = useDerivedValue(() => {
    const point = trajectoryPointAt(track, progress.value);
    return { x: point.px, y: point.py };
  });

  return (
    <>
      {/* Only the arrows this scene uses get a per-frame path. */}
      {arrows.map((kind) => (
        <DerivedArrow
          key={kind}
          kind={kind}
          at={at}
          track={track}
          closed={closed}
          maxSpeed={maxSpeed}
          radius={radius}
          centre={centre}
          slope={slope}
          progress={progress}
          color={kind === "velocity" ? color : theme.textSecondary}
          canvasWidth={canvasWidth}
          canvasHeight={canvasHeight}
        />
      ))}
      <Circle c={at} r={radius + 1.5} color={theme.bg} />
      <Circle c={at} r={radius} color={color} />
    </>
  );
}

function DerivedArrow({
  kind,
  at,
  track,
  closed,
  maxSpeed,
  radius,
  centre,
  slope,
  progress,
  color,
  canvasWidth,
  canvasHeight,
}: {
  kind: SimulationArrow;
  /** The body's centre this frame, shared with the body's disc. */
  at: SharedValue<{ x: number; y: number }>;
  track: ScreenPoint[];
  closed: boolean;
  maxSpeed: number;
  radius: number;
  centre: ScreenPoint | null;
  slope: Slope | null;
  progress: SharedValue<number>;
  color: string;
  canvasWidth: number;
  canvasHeight: number;
}) {
  const head = kind === "velocity" ? "open" : "filled";
  const path = useDerivedValue(() => {
    const centreNow = { px: at.value.x, py: at.value.y };
    const arrow = derivedArrowGeometry(kind, centreNow, radius, {
      tangent: kind === "velocity" ? tangentAt(track, progress.value, closed) : { dx: 0, dy: 0 },
      maxSpeed,
      centre,
      slope,
      width: canvasWidth,
      height: canvasHeight,
    });
    if (!arrow) return Skia.Path.Make();
    return arrowPath(
      arrow.fromX,
      arrow.fromY,
      arrow.ux,
      arrow.uy,
      arrow.length,
      arrowHeadSize(arrow.length),
      head,
    );
  });
  return (
    <>
      <Path
        path={path}
        color={color}
        style="stroke"
        strokeWidth={ARROW_STROKE}
        strokeJoin="round"
        strokeCap="round"
      />
      {head === "filled" ? <Path path={path} color={color} style="fill" /> : null}
    </>
  );
}

function BodyLabel({
  text,
  layout,
  track,
  progress,
  font,
  theme,
  canvasWidth,
  canvasHeight,
}: {
  text: string;
  layout: BodyLabelLayout;
  track: ScreenPoint[];
  progress: SharedValue<number>;
  font: SkFont;
  theme: Theme;
  canvasWidth: number;
  canvasHeight: number;
}) {
  const at = useDerivedValue(() => trajectoryPointAt(track, progress.value));
  const x = useDerivedValue(() =>
    clampCanvasLabelX(at.value.px + layout.dx, layout.width, canvasWidth),
  );
  const y = useDerivedValue(() =>
    clampCanvasLabelBaseline(at.value.py + layout.dy, LABEL_FONT_SIZE, canvasHeight),
  );
  return (
    <HaloText x={x} y={y} text={text} font={font} color={theme.textSecondary} halo={theme.bg} />
  );
}

function StatedVector({ layout, theme }: { layout: VectorLayout; theme: Theme }) {
  const stroke = vectorStroke(layout.vector.role);
  const color = vectorColor(layout, theme);
  const strokeWidth = layout.vector.role === "result" ? RESULT_STROKE : ARROW_STROKE;
  const paths = useMemo(() => {
    const { from, tip, head } = layout;
    const length = Math.hypot(tip.px - from.px, tip.py - from.py);
    if (!(length > 0)) return null;
    const ux = (tip.px - from.px) / length;
    const uy = (tip.py - from.py) / length;
    if (stroke === "force") {
      return { solid: true as const, whole: arrowPath(from.px, from.py, ux, uy, length, head, "filled") };
    }
    // A dashed shaft with a solid end: dashing the head would break it up.
    return {
      solid: false as const,
      shaft: arrowShaftPath(from.px, from.py, ux, uy, length),
      head: arrowHeadPath(from.px, from.py, ux, uy, length, head, stroke === "motion" ? "open" : "ticks"),
    };
  }, [layout, stroke]);
  if (!paths) return null;

  if (paths.solid) {
    return (
      <>
        <Path
          path={paths.whole}
          color={color}
          style="stroke"
          strokeWidth={strokeWidth}
          strokeJoin="round"
          strokeCap="round"
        />
        <Path path={paths.whole} color={color} style="fill" />
      </>
    );
  }
  return (
    <>
      <Path path={paths.shaft} color={color} style="stroke" strokeWidth={strokeWidth}>
        <DashPathEffect intervals={stroke === "motion" ? [5, 3] : [3, 3]} />
      </Path>
      <Path
        path={paths.head}
        color={color}
        style="stroke"
        strokeWidth={strokeWidth}
        strokeJoin="round"
        strokeCap="round"
      />
    </>
  );
}

function SceneMarkers({
  spec,
  surface,
  centre,
  beam,
  pivot,
  spring,
  reduceMotion,
}: {
  spec: SimulationSpec;
  surface: boolean;
  centre: boolean;
  beam: boolean;
  pivot: boolean;
  spring: boolean;
  reduceMotion: boolean;
}) {
  return (
    <View
      pointerEvents="none"
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
      style={StyleSheet.absoluteFill}
    >
      {surface ? <View testID="simulation-slope" style={markerStyle} /> : null}
      {spec.ground ? <View testID="simulation-ground" style={markerStyle} /> : null}
      {beam ? <View testID="simulation-beam" style={markerStyle} /> : null}
      {pivot ? <View testID="simulation-pivot" style={markerStyle} /> : null}
      {centre ? <View testID="simulation-centre" style={markerStyle} /> : null}
      {spring ? <View testID="simulation-spring" style={markerStyle} /> : null}
      {reduceMotion ? <View testID="simulation-static" style={markerStyle} /> : null}
      {spec.bodies.map((body, bodyIndex) => (
        <View key={`body-marker-${bodyIndex}`}>
          <View testID="simulation-body" style={markerStyle} />
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
    title: figureTitleStyle(theme),
    fallback: {
      marginVertical: Space.xs,
      padding: Space.sm,
      borderRadius: Radius.md,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
    },
    fallbackText: {
      ...Type.compact,
      color: theme.textSecondary,
    },
  });
}

export type { SimulationSpec, SimulationTransform };
