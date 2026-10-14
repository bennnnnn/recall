/** Native Skia renderer for verified physics simulation scenes. */
import { useCallback, useMemo } from "react";
import { StyleSheet, Text, useWindowDimensions, View } from "react-native";
import { useTranslation } from "react-i18next";
import {
  Canvas,
  Circle,
  DashPathEffect,
  Group,
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
  FLUID_TINT,
  inclineDirections,
  inclineSurface,
  inclineWedge,
  layoutSimulationScene,
  parseSimulationSpec,
  PIVOT_SIZE,
  placeNudgedLabel,
  riddenVectorGeometry,
  sceneTitle,
  SIMULATION_HEIGHT,
  SIMULATION_MIN_HEIGHT,
  SIMULATION_PAD,
  simulationAccessibilityLabel,
  simulationIsAnimated,
  simulationTransform,
  simulationViewportHeight,
  tangentAt,
  tetherEnd,
  derivedLabelOrigin,
  vectorLabelOrigin,
  vectorStroke,
  worldToScreen,
  type AngleLayout,
  type ArrowLabelLayout,
  type BodyLabelLayout,
  type PlacedLabel,
  type SceneLayout,
  type SimulationArrow,
  type SimulationSpec,
  type SimulationTransform,
  type ScreenPoint,
  type SolidLayout,
  type SupportLayout,
  type VectorLayout,
} from "@/lib/physics/simulation";
import { trajectoryPointAt } from "@/lib/math/trajectory";
import { Motion } from "@/lib/motion";
import { Theme, useTheme, withAlpha } from "@/lib/theme";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Type } from "@/lib/type";
import { figureTitleStyle, figureWidth } from "@/components/rich/figure";
import { PlaybackButton } from "@/components/rich/PlaybackButton";
import { usePlayback } from "@/components/rich/usePlayback";
import { HaloText } from "@/components/rich/skia/HaloText";
import { measureRuns } from "@/components/rich/skia/fontRuns";
import {
  appendArrowHead,
  arrowHeadPath,
  arrowPath,
  arrowShaftPath,
  linePath,
  pointsPath,
} from "@/components/rich/skia/paths";

export { SIMULATION_HEIGHT, SIMULATION_MIN_HEIGHT, SIMULATION_PAD };

const LABEL_FONT_SIZE = 11;
/** The math faces set a size larger, so a τ stands as tall as SpaceMono's x-height beside it. */
const FALLBACK_FONT_SIZE = 13;
/** Until the font loads, a rough SpaceMono advance keeps the layout sane. */
const FALLBACK_CHAR_WIDTH = 6.7;
const WALL_HALF_HEIGHT = 16;
const CENTRE_DOT_RADIUS = 3;
const ARROW_STROKE = 1.5;
const RESULT_STROKE = 2.5;
const HUB_RADIUS = 2.5;
/** How strongly a strobe copy shows: enough to read the spacing, never a second body. */
const STROBE_OPACITY = 0.28;

/** Periodic motion goes round again while playing; the rest hold their end. */
const PERIODIC: readonly SimulationSpec["type"][] = ["orbit", "spring", "pendulum"];

/**
 * The invisible geometry markers exist for component tests, which cannot see
 * inside a Skia canvas. They are never shipped to a screen reader.
 */
const RENDER_TEST_MARKERS = process.env.NODE_ENV === "test";

type Props = { content: string };
type Slope = ReturnType<typeof inclineDirections>;
type Rect = { x: number; y: number; width: number; height: number };

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

function polygonPath(points: readonly ScreenPoint[]) {
  const path = Skia.Path.Make();
  points.forEach((point, index) => {
    if (index === 0) path.moveTo(point.px, point.py);
    else path.lineTo(point.px, point.py);
  });
  path.close();
  return path;
}

function rectPath(rect: Rect) {
  return polygonPath([
    { px: rect.x, py: rect.y },
    { px: rect.x + rect.width, py: rect.y },
    { px: rect.x + rect.width, py: rect.y + rect.height },
    { px: rect.x, py: rect.y + rect.height },
  ]);
}

function segmentsPath(segments: SupportLayout["hatches"]) {
  const path = Skia.Path.Make();
  for (const segment of segments) {
    path.moveTo(segment.x1, segment.y1);
    path.lineTo(segment.x2, segment.y2);
  }
  return path;
}

/** A box body: a square of side 2 * `half`, turned `angle` radians on screen. */
function boxPath(cx: number, cy: number, half: number, angle: number) {
  "worklet";
  const c = Math.cos(angle) * half;
  const s = Math.sin(angle) * half;
  const path = Skia.Path.Make();
  // Corners at ±along ±across, where along = (c, s) and across = (−s, c).
  path.moveTo(cx + c - s, cy + s + c);
  path.lineTo(cx - c - s, cy - s + c);
  path.lineTo(cx - c + s, cy - s - c);
  path.lineTo(cx + c + s, cy + s - c);
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
  // SpaceMono has no Greek: τ, θ, λ and Ω come from the math faces instead,
  // upright for units and capitals, italic for lower-case variables.
  const upright = useFont(require("../../assets/fonts/KaTeX_Main-Regular.ttf"), FALLBACK_FONT_SIZE);
  const italic = useFont(require("../../assets/fonts/KaTeX_Math-Italic.ttf"), FALLBACK_FONT_SIZE);
  const fallbacks = useMemo(() => [upright, italic], [italic, upright]);
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
  const animated = useMemo(() => (spec ? simulationIsAnimated(spec) : false), [spec]);
  const measure = useCallback(
    (text: string) =>
      font
        ? measureRuns(text, [font, ...fallbacks.filter((face): face is SkFont => face !== null)])
        : text.length * FALLBACK_CHAR_WIDTH,
    [fallbacks, font],
  );
  const layout = useMemo(
    () =>
      spec && transform
        ? layoutSimulationScene(spec, transform, width, height, measure, LABEL_FONT_SIZE)
        : null,
    [height, measure, spec, transform, width],
  );
  // A spring's coil already runs along its path, so a trail would only
  // stripe the coil.
  const trackPaths = useMemo(
    () => (spec?.type === "spring" || !layout ? [] : layout.tracks.map(pointsPath)),
    [layout, spec],
  );
  const description = useMemo(() => (spec ? simulationAccessibilityLabel(spec, t) : ""), [spec, t]);
  const title = useMemo(() => (spec ? sceneTitle(spec, t) : ""), [spec, t]);
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

  const { tracks, closed, maxSpeed, floorY, obstacles } = layout;
  const centre = spec.centre ? worldToScreen(spec.centre.x, spec.centre.y, transform) : null;
  const groundY = worldToScreen(0, 0, transform).py;
  const surface = inclineSurface(spec, transform);
  const wedge = inclineWedge(spec, transform);
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
  const fluid = theme.isDark ? FLUID_TINT.dark : FLUID_TINT.light;
  const solidFill = withAlpha(theme.textTertiary, 0.14);
  const wheel = layout.pulley
    ? { cx: layout.pulley.centre.px, cy: layout.pulley.centre.py, radius: layout.pulley.radius }
    : null;

  return (
    <View style={styles.wrap}>
      <Text style={styles.title}>{title}</Text>
      <View
        accessible
        accessibilityRole="image"
        accessibilityLabel={description}
        style={{ width, height }}
      >
        <Canvas testID="simulation-canvas" style={{ width, height }}>
          {/* Solids and fluids sit behind everything else. */}
          {layout.solids.map((solid, index) => (
            <SolidShape
              key={`solid-${index}`}
              layout={solid}
              fill={
                solid.solid.kind === "fluid"
                  ? withAlpha(fluid, theme.isDark ? 0.22 : 0.16)
                  : solidFill
              }
              edge={solid.solid.kind === "fluid" ? fluid : theme.textTertiary}
            />
          ))}
          {layout.planet ? (
            <>
              <Circle
                cx={layout.planet.centre.px}
                cy={layout.planet.centre.py}
                r={layout.planet.radius}
                color={planetFill(theme)}
              />
              <Circle
                cx={layout.planet.centre.px}
                cy={layout.planet.centre.py}
                r={layout.planet.radius}
                color={withAlpha(theme.textTertiary, 0.55)}
                style="stroke"
                strokeWidth={1}
              />
            </>
          ) : null}
          {wedge ? <Path path={polygonPath(wedge)} color={solidFill} /> : null}
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
          {layout.pulley ? <PulleyWheel layout={layout.pulley} theme={theme} /> : null}
          {layout.tethers.map((tether, index) =>
            tether.support ? (
              <Support key={`support-${index}`} layout={tether.support} theme={theme} />
            ) : null,
          )}
          {layout.angles.map((angle, index) => (
            <AngleArc key={`angle-${index}`} layout={angle} theme={theme} />
          ))}
          {layout.vectors.map((vector, index) =>
            vector.body !== null ? (
              <RidingVector
                key={`vector-${index}`}
                layout={vector}
                track={tracks[vector.body]}
                progress={progress}
                wheel={wheel}
                theme={theme}
                canvasWidth={width}
                canvasHeight={height}
              />
            ) : (
              <StatedVector key={`vector-${index}`} layout={vector} theme={theme} />
            ),
          )}
          {centre && !layout.planet ? (
            <Circle cx={centre.px} cy={centre.py} r={CENTRE_DOT_RADIUS} color={theme.textSecondary} />
          ) : null}
          {spec.bodies.map((body, index) =>
            layout.strobes[index].map((point, copy) => (
              <BodyShape
                key={`strobe-${index}-${copy}`}
                at={point}
                radius={layout.radii[index]}
                boxAngle={layout.boxAngles[index]}
                color={bodyColor(body.role)}
                opacity={STROBE_OPACITY}
              />
            )),
          )}
          {layout.restLines.map((line, index) => (
            <Path
              key={`rest-${index}`}
              path={linePath(line.x1, line.y1, line.x2, line.y2)}
              color={theme.textTertiary}
              style="stroke"
              strokeWidth={1}
            >
              <DashPathEffect intervals={[3, 3]} />
            </Path>
          ))}
          {layout.tethers.map((tether, index) => (
            <Tether
              key={`tether-${index}`}
              anchor={tether.anchor}
              track={tracks[tether.body]}
              radius={layout.radii[tether.body]}
              boxAngle={layout.boxAngles[tether.body]}
              progress={progress}
              color={theme.textSecondary}
            />
          ))}
          {spec.bodies.map((body, index) => (
            <BodyMarks
              key={`body-${index}`}
              track={tracks[index]}
              closed={closed[index]}
              maxSpeed={maxSpeed}
              radius={layout.radii[index]}
              boxAngle={layout.boxAngles[index]}
              color={bodyColor(body.role)}
              arrows={spec.arrows}
              centre={centre}
              slope={slope}
              floorY={floorY}
              obstacles={obstacles}
              progress={progress}
              theme={theme}
              canvasWidth={width}
              canvasHeight={height}
            />
          ))}
          {/* Labels last, over every line, each with a halo so nothing strikes it through. */}
          {font ? (
            <SceneLabels
              spec={spec}
              layout={layout}
              font={font}
              fallbacks={fallbacks}
              wheel={wheel}
              theme={theme}
              progress={progress}
              centre={centre}
              slope={slope}
              canvasWidth={width}
              canvasHeight={height}
            />
          ) : null}
        </Canvas>
        {RENDER_TEST_MARKERS ? (
          <SceneMarkers
            spec={spec}
            layout={layout}
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

/** The planet's muted disc, as one opaque colour so its label's halo can match it. */
function planetFill(theme: Theme): string {
  return mixColor(theme.bg, theme.textTertiary, 0.2);
}

/** `a` moved `amount` of the way to `b`; both `#rrggbb`. Anything else returns `b` washed. */
function mixColor(a: string, b: string, amount: number): string {
  const parse = (hex: string) => {
    const match = /^#([0-9a-f]{6})$/i.exec(hex);
    if (!match) return null;
    const value = parseInt(match[1], 16);
    return [(value >> 16) & 255, (value >> 8) & 255, value & 255];
  };
  const from = parse(a);
  const to = parse(b);
  if (!from || !to) return withAlpha(b, amount);
  const mixed = from.map((channel, i) => Math.round(channel + (to[i] - channel) * amount));
  return `rgb(${mixed[0]}, ${mixed[1]}, ${mixed[2]})`;
}

function vectorColor(role: VectorLayout["vector"]["role"], theme: Theme): string {
  // Motion shares the velocity arrow's colour family; the answer is primary.
  return role === "result" || role === "motion" ? theme.primary : theme.textSecondary;
}

function SolidShape({ layout, fill, edge }: { layout: SolidLayout; fill: string; edge: string }) {
  const { box, solid } = layout;
  if (solid.kind === "fluid") {
    // A tank of water: a wash of blue with its surface drawn along the top.
    return (
      <>
        <Path path={rectPath(box)} color={fill} />
        <Path
          path={linePath(box.x, box.y, box.x + box.width, box.y)}
          color={edge}
          style="stroke"
          strokeWidth={ARROW_STROKE}
        />
      </>
    );
  }
  return (
    <>
      <Path path={rectPath(box)} color={fill} />
      <Path path={rectPath(box)} color={edge} style="stroke" strokeWidth={1} />
    </>
  );
}

function PulleyWheel({
  layout,
  theme,
}: {
  layout: NonNullable<SceneLayout["pulley"]>;
  theme: Theme;
}) {
  const { centre, radius, rope } = layout;
  return (
    <>
      {/* The bracket it hangs from, up to the top of the canvas. */}
      <Path
        path={linePath(centre.px, centre.py, centre.px, 0)}
        color={theme.textSecondary}
        style="stroke"
        strokeWidth={2}
      />
      <Circle cx={centre.px} cy={centre.py} r={radius} color={theme.bg} />
      <Circle
        cx={centre.px}
        cy={centre.py}
        r={radius}
        color={theme.textSecondary}
        style="stroke"
        strokeWidth={ARROW_STROKE}
      />
      <Circle cx={centre.px} cy={centre.py} r={HUB_RADIUS} color={theme.textSecondary} />
      {rope ? (
        <Path
          path={pointsPath(rope)}
          color={theme.textSecondary}
          style="stroke"
          strokeWidth={ARROW_STROKE * 1.5}
          strokeCap="round"
        />
      ) : null}
    </>
  );
}

function Support({ layout, theme }: { layout: SupportLayout; theme: Theme }) {
  return (
    <>
      <Path
        path={segmentsPath(layout.hatches)}
        color={theme.textTertiary}
        style="stroke"
        strokeWidth={1}
      />
      <Path
        path={linePath(layout.bar.x1, layout.bar.y1, layout.bar.x2, layout.bar.y2)}
        color={theme.textSecondary}
        style="stroke"
        strokeWidth={2}
        strokeCap="round"
      />
    </>
  );
}

function AngleArc({ layout, theme }: { layout: AngleLayout; theme: Theme }) {
  const result = layout.angle.role === "result";
  const color = result ? theme.primary : theme.textSecondary;
  const strokeWidth = result ? RESULT_STROKE : ARROW_STROKE;
  const paths = useMemo(() => {
    const arc = pointsPath(layout.arc);
    const head = layout.head
      ? appendArrowHead(
          Skia.Path.Make(),
          layout.head.tip.px,
          layout.head.tip.py,
          layout.head.ux,
          layout.head.uy,
          layout.head.size,
          "filled",
        )
      : null;
    return { arc, head };
  }, [layout]);
  return (
    <>
      <Path
        path={paths.arc}
        color={color}
        style="stroke"
        strokeWidth={strokeWidth}
        strokeCap="round"
        strokeJoin="round"
      />
      {paths.head ? (
        <>
          <Path
            path={paths.head}
            color={color}
            style="stroke"
            strokeWidth={ARROW_STROKE}
            strokeJoin="round"
          />
          <Path path={paths.head} color={color} style="fill" />
        </>
      ) : null}
    </>
  );
}

type Wheel = { cx: number; cy: number; radius: number } | null;

/** A riding vector this frame: started where its body has carried it, refitted. */
function ridingNow(
  layout: VectorLayout,
  track: ScreenPoint[],
  progress: number,
  wheel: Wheel,
  canvasWidth: number,
  canvasHeight: number,
) {
  "worklet";
  const ride = layout.ride;
  if (!ride) return null;
  const now = trajectoryPointAt(track, progress);
  const fromX = layout.from.px + now.px - track[0].px;
  const fromY = layout.from.py + now.py - track[0].py;
  const fit = riddenVectorGeometry(
    fromX,
    fromY,
    ride.ux,
    ride.uy,
    ride.desired,
    canvasWidth,
    canvasHeight,
    wheel,
  );
  return fit ? { fromX, fromY, ux: ride.ux, uy: ride.uy, length: fit.length } : null;
}

/** A stated vector riding on a moving body: the tension on an Atwood mass goes where it goes. */
function RidingVector({
  layout,
  track,
  progress,
  wheel,
  theme,
  canvasWidth,
  canvasHeight,
}: {
  layout: VectorLayout;
  track: ScreenPoint[];
  progress: SharedValue<number>;
  wheel: Wheel;
  theme: Theme;
  canvasWidth: number;
  canvasHeight: number;
}) {
  const stroke = vectorStroke(layout.vector.role);
  const color = vectorColor(layout.vector.role, theme);
  const strokeWidth = layout.vector.role === "result" ? RESULT_STROKE : ARROW_STROKE;
  const shaft = useDerivedValue(() => {
    const path = Skia.Path.Make();
    const arrow = ridingNow(layout, track, progress.value, wheel, canvasWidth, canvasHeight);
    if (!arrow) return path;
    if (stroke === "force") {
      return arrowPath(
        arrow.fromX,
        arrow.fromY,
        arrow.ux,
        arrow.uy,
        arrow.length,
        arrowHeadSize(arrow.length),
        "filled",
      );
    }
    path.moveTo(arrow.fromX, arrow.fromY);
    path.lineTo(arrow.fromX + arrow.ux * arrow.length, arrow.fromY + arrow.uy * arrow.length);
    return path;
  });
  const head = useDerivedValue(() => {
    const path = Skia.Path.Make();
    const arrow = ridingNow(layout, track, progress.value, wheel, canvasWidth, canvasHeight);
    if (!arrow || stroke === "force") return path;
    return appendArrowHead(
      path,
      arrow.fromX + arrow.ux * arrow.length,
      arrow.fromY + arrow.uy * arrow.length,
      arrow.ux,
      arrow.uy,
      arrowHeadSize(arrow.length),
      stroke === "motion" ? "open" : "ticks",
      arrow.length,
    );
  });
  if (stroke === "force") {
    return (
      <>
        <Path
          path={shaft}
          color={color}
          style="stroke"
          strokeWidth={strokeWidth}
          strokeJoin="round"
          strokeCap="round"
        />
        <Path path={shaft} color={color} style="fill" />
      </>
    );
  }
  return (
    <>
      <Path path={shaft} color={color} style="stroke" strokeWidth={strokeWidth}>
        <DashPathEffect intervals={stroke === "motion" ? [5, 3] : [3, 3]} />
      </Path>
      <Path
        path={head}
        color={color}
        style="stroke"
        strokeWidth={strokeWidth}
        strokeJoin="round"
        strokeCap="round"
      />
    </>
  );
}

/** A riding vector's label, set from its arrow every frame and hidden with it. */
function RidingVectorLabel({
  layout,
  track,
  progress,
  wheel,
  font,
  fallbacks,
  theme,
  canvasWidth,
  canvasHeight,
}: {
  layout: VectorLayout;
  track: ScreenPoint[];
  progress: SharedValue<number>;
  wheel: Wheel;
  font: SkFont;
  fallbacks: readonly (SkFont | null)[];
  theme: Theme;
  canvasWidth: number;
  canvasHeight: number;
}) {
  const spot = useDerivedValue(() => {
    const ride = layout.ride;
    const arrow = ridingNow(layout, track, progress.value, wheel, canvasWidth, canvasHeight);
    if (!arrow || !ride) return { x: 0, y: 0, shown: 0 };
    const origin = vectorLabelOrigin(
      arrow.fromX,
      arrow.fromY,
      arrow.fromX + arrow.ux * arrow.length,
      arrow.fromY + arrow.uy * arrow.length,
      ride.labelWidth,
      LABEL_FONT_SIZE,
      ride.mid,
      ride.side,
      ride.beside,
    );
    const place = placeNudgedLabel(
      origin.x,
      origin.y,
      ride.labelWidth,
      LABEL_FONT_SIZE,
      ride.dx,
      ride.dy,
      canvasWidth,
      canvasHeight,
    );
    return { x: place.x, y: place.baseline, shown: 1 };
  });
  const x = useDerivedValue(() => spot.value.x);
  const y = useDerivedValue(() => spot.value.y);
  const opacity = useDerivedValue(() => spot.value.shown);
  return (
    <Group opacity={opacity}>
      <HaloText
        x={x}
        y={y}
        text={layout.vector.label ?? ""}
        font={font}
        fallbacks={fallbacks}
        color={vectorColor(layout.vector.role, theme)}
        halo={theme.bg}
      />
    </Group>
  );
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

function Tether({
  anchor,
  track,
  radius,
  boxAngle,
  progress,
  color,
}: {
  anchor: ScreenPoint;
  track: ScreenPoint[];
  radius: number;
  boxAngle: number | null;
  progress: SharedValue<number>;
  color: string;
}) {
  const path = useDerivedValue(() => {
    const end = tetherEnd(anchor, trajectoryPointAt(track, progress.value), radius, boxAngle);
    const line = Skia.Path.Make();
    if (!end) return line;
    line.moveTo(anchor.px, anchor.py);
    line.lineTo(end.px, end.py);
    return line;
  });
  return (
    <Path path={path} color={color} style="stroke" strokeWidth={ARROW_STROKE} strokeCap="round" />
  );
}

/** A body's disc or box, with a halo of the background so lines behind it break around it. */
function BodyShape({
  at,
  radius,
  boxAngle,
  color,
  halo,
  opacity,
}: {
  at: ScreenPoint | SharedValue<{ x: number; y: number }>;
  radius: number;
  boxAngle: number | null;
  color: string;
  halo?: string;
  opacity?: number;
}) {
  const point = "px" in at ? at : null;
  const live = "px" in at ? null : at;
  const box = useDerivedValue(() => {
    if (boxAngle === null) return Skia.Path.Make();
    const x = live ? live.value.x : point!.px;
    const y = live ? live.value.y : point!.py;
    return boxPath(x, y, radius, boxAngle);
  });
  const c = live ?? { x: point!.px, y: point!.py };
  if (boxAngle !== null) {
    return (
      <Group opacity={opacity ?? 1}>
        {halo ? (
          <Path path={box} color={halo} style="stroke" strokeWidth={3} strokeJoin="round" />
        ) : null}
        <Path path={box} color={color} />
      </Group>
    );
  }
  return (
    <Group opacity={opacity ?? 1}>
      {halo ? <Circle c={c} r={radius + 1.5} color={halo} /> : null}
      <Circle c={c} r={radius} color={color} />
    </Group>
  );
}

function BodyMarks({
  track,
  closed,
  maxSpeed,
  radius,
  boxAngle,
  color,
  arrows,
  centre,
  slope,
  floorY,
  obstacles,
  progress,
  theme,
  canvasWidth,
  canvasHeight,
}: {
  track: ScreenPoint[];
  closed: boolean;
  maxSpeed: number;
  radius: number;
  boxAngle: number | null;
  color: string;
  arrows: SimulationArrow[];
  centre: ScreenPoint | null;
  slope: Slope | null;
  floorY: number | null;
  obstacles: Rect[];
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
          boxAngle={boxAngle}
          centre={centre}
          slope={slope}
          floorY={floorY}
          obstacles={obstacles}
          progress={progress}
          color={kind === "velocity" ? color : theme.textSecondary}
          canvasWidth={canvasWidth}
          canvasHeight={canvasHeight}
        />
      ))}
      <BodyShape at={at} radius={radius} boxAngle={boxAngle} color={color} halo={theme.bg} />
    </>
  );
}

type ArrowContext = {
  track: ScreenPoint[];
  closed: boolean;
  maxSpeed: number;
  radius: number;
  boxAngle: number | null;
  centre: ScreenPoint | null;
  slope: Slope | null;
  floorY: number | null;
  obstacles: Rect[];
  canvasWidth: number;
  canvasHeight: number;
};

function arrowNow(kind: SimulationArrow, at: ScreenPoint, progress: number, context: ArrowContext) {
  "worklet";
  return derivedArrowGeometry(kind, at, context.radius, {
    tangent:
      kind === "velocity" ? tangentAt(context.track, progress, context.closed) : { dx: 0, dy: 0 },
    maxSpeed: context.maxSpeed,
    centre: context.centre,
    slope: context.slope,
    width: context.canvasWidth,
    height: context.canvasHeight,
    boxAngle: context.boxAngle,
    floorY: context.floorY,
    solids: context.obstacles,
  });
}

function DerivedArrow({
  kind,
  at,
  progress,
  color,
  ...context
}: {
  kind: SimulationArrow;
  /** The body's centre this frame, shared with the body's disc. */
  at: SharedValue<{ x: number; y: number }>;
  progress: SharedValue<number>;
  color: string;
} & ArrowContext) {
  const head = kind === "velocity" ? "open" : "filled";
  const path = useDerivedValue(() => {
    const arrow = arrowNow(kind, { px: at.value.x, py: at.value.y }, progress.value, context);
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

/** Every label in the scene, drawn over every line. */
function SceneLabels({
  spec,
  layout,
  font,
  fallbacks,
  wheel,
  theme,
  progress,
  centre,
  slope,
  canvasWidth,
  canvasHeight,
}: {
  spec: SimulationSpec;
  layout: SceneLayout;
  font: SkFont;
  fallbacks: readonly (SkFont | null)[];
  wheel: Wheel;
  theme: Theme;
  progress: SharedValue<number>;
  centre: ScreenPoint | null;
  slope: Slope | null;
  canvasWidth: number;
  canvasHeight: number;
}) {
  const fixedLabel = (label: PlacedLabel, key: string, color: string, halo = theme.bg) => (
    <HaloText
      key={key}
      x={label.x}
      y={label.y}
      text={label.text}
      font={font}
      fallbacks={fallbacks}
      color={color}
      halo={halo}
    />
  );
  const planet = layout.planet;
  // A name inside the planet is haloed in the planet's own colour, so an
  // arrow crossing it breaks around the word without a pale patch.
  const planetInside =
    planet !== null &&
    planet.label !== null &&
    planet.label.box.y < planet.centre.py + planet.radius;
  return (
    <>
      {layout.solids.map((solid, index) =>
        solid.label ? fixedLabel(solid.label, `solid-label-${index}`, theme.textSecondary) : null,
      )}
      {planet?.label
        ? fixedLabel(
            planet.label,
            "planet-label",
            theme.textSecondary,
            planetInside ? planetFill(theme) : theme.bg,
          )
        : null}
      {layout.angles.map((angle, index) =>
        angle.label
          ? fixedLabel(
              angle.label,
              `angle-label-${index}`,
              angle.angle.role === "result" ? theme.primary : theme.textSecondary,
            )
          : null,
      )}
      {layout.vectors.map((vector, index) => {
        if (!vector.label) return null;
        return vector.body !== null ? (
          <RidingVectorLabel
            key={`vector-label-${index}`}
            layout={vector}
            track={layout.tracks[vector.body]}
            progress={progress}
            wheel={wheel}
            font={font}
            fallbacks={fallbacks}
            theme={theme}
            canvasWidth={canvasWidth}
            canvasHeight={canvasHeight}
          />
        ) : (
          fixedLabel(vector.label, `vector-label-${index}`, vectorColor(vector.vector.role, theme))
        );
      })}
      {layout.arrowLabels.map((label, index) => (
        <DerivedArrowLabel
          key={`arrow-label-${index}`}
          label={label}
          font={font}
          fallbacks={fallbacks}
          theme={theme}
          progress={progress}
          color={
            label.kind === "velocity" ? bodyTint(spec, label.body, theme) : theme.textSecondary
          }
          track={layout.tracks[label.body]}
          closed={layout.closed[label.body]}
          maxSpeed={layout.maxSpeed}
          radius={layout.radii[label.body]}
          boxAngle={layout.boxAngles[label.body]}
          centre={centre}
          slope={slope}
          floorY={layout.floorY}
          obstacles={layout.obstacles}
          canvasWidth={canvasWidth}
          canvasHeight={canvasHeight}
        />
      ))}
      {spec.bodies.map((body, index) => {
        const label = layout.bodyLabels[index];
        return body.label && label ? (
          <BodyLabel
            key={`body-label-${index}`}
            text={body.label}
            layout={label}
            track={layout.tracks[index]}
            progress={progress}
            font={font}
            fallbacks={fallbacks}
            theme={theme}
            canvasWidth={canvasWidth}
            canvasHeight={canvasHeight}
          />
        ) : null;
      })}
    </>
  );
}

function bodyTint(spec: SimulationSpec, body: number, theme: Theme): string {
  return spec.bodies[body]?.role === "secondary" ? theme.graphSeries[1] : theme.primary;
}

/** A derived arrow's label, following its tip every frame; hidden with the arrow. */
function DerivedArrowLabel({
  label,
  font,
  fallbacks,
  theme,
  progress,
  color,
  ...context
}: {
  label: ArrowLabelLayout;
  font: SkFont;
  fallbacks: readonly (SkFont | null)[];
  theme: Theme;
  progress: SharedValue<number>;
  color: string;
} & ArrowContext) {
  const spot = useDerivedValue(() => {
    const at = trajectoryPointAt(context.track, progress.value);
    const arrow = arrowNow(label.kind, at, progress.value, context);
    if (!arrow) return { x: 0, y: 0, shown: 0 };
    const origin = derivedLabelOrigin(
      arrow,
      label.width,
      LABEL_FONT_SIZE,
      context.floorY,
      context.obstacles,
      label.beside,
    );
    const place = placeNudgedLabel(
      origin.x,
      origin.y,
      label.width,
      LABEL_FONT_SIZE,
      label.dx,
      label.dy,
      context.canvasWidth,
      context.canvasHeight,
    );
    return { x: place.x, y: place.baseline, shown: 1 };
  });
  const x = useDerivedValue(() => spot.value.x);
  const y = useDerivedValue(() => spot.value.y);
  const opacity = useDerivedValue(() => spot.value.shown);
  return (
    <Group opacity={opacity}>
      <HaloText
        x={x}
        y={y}
        text={label.text}
        font={font}
        fallbacks={fallbacks}
        color={color}
        halo={theme.bg}
      />
    </Group>
  );
}

function BodyLabel({
  text,
  layout,
  track,
  progress,
  font,
  fallbacks,
  theme,
  canvasWidth,
  canvasHeight,
}: {
  text: string;
  layout: BodyLabelLayout;
  track: ScreenPoint[];
  progress: SharedValue<number>;
  font: SkFont;
  fallbacks: readonly (SkFont | null)[];
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
    <HaloText
      x={x}
      y={y}
      text={text}
      font={font}
      fallbacks={fallbacks}
      color={theme.textSecondary}
      halo={theme.bg}
    />
  );
}

function StatedVector({ layout, theme }: { layout: VectorLayout; theme: Theme }) {
  const stroke = vectorStroke(layout.vector.role);
  const color = vectorColor(layout.vector.role, theme);
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
  layout,
  surface,
  centre,
  beam,
  pivot,
  spring,
  reduceMotion,
}: {
  spec: SimulationSpec;
  layout: SceneLayout;
  surface: boolean;
  centre: boolean;
  beam: boolean;
  pivot: boolean;
  spring: boolean;
  reduceMotion: boolean;
}) {
  const marker = (testID: string, key?: string) => (
    <View key={key ?? testID} testID={testID} style={markerStyle} />
  );
  return (
    <View
      pointerEvents="none"
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
      style={StyleSheet.absoluteFill}
    >
      {surface ? marker("simulation-slope") : null}
      {spec.ground ? marker("simulation-ground") : null}
      {beam ? marker("simulation-beam") : null}
      {pivot ? marker("simulation-pivot") : null}
      {centre ? marker("simulation-centre") : null}
      {spring ? marker("simulation-spring") : null}
      {reduceMotion ? marker("simulation-static") : null}
      {layout.pulley ? marker("simulation-pulley") : null}
      {layout.planet ? marker("simulation-planet") : null}
      {layout.tethers.map((tether, index) => (
        <View key={`tether-marker-${index}`} testID="simulation-tether" style={markerStyle}>
          {tether.support ? marker("simulation-support") : null}
        </View>
      ))}
      {layout.angles.map((angle, index) => (
        <View
          key={`angle-marker-${index}`}
          testID={`simulation-angle-${angle.angle.role}`}
          style={markerStyle}
        >
          {angle.head ? marker("simulation-angle-arrow") : null}
          {angle.label ? marker("simulation-angle-label") : null}
        </View>
      ))}
      {layout.solids.map((solid, index) =>
        marker(`simulation-solid-${solid.solid.kind}`, `solid-marker-${index}`),
      )}
      {layout.arrowLabels.map((label, index) =>
        marker(`simulation-arrow-label-${label.kind}`, `arrow-label-marker-${index}`),
      )}
      {spec.bodies.map((body, bodyIndex) => (
        <View key={`body-marker-${bodyIndex}`}>
          <View testID="simulation-body" style={markerStyle} />
          {layout.boxAngles[bodyIndex] !== null ? marker("simulation-body-box") : null}
          {body.label ? <View testID="simulation-body-label" style={markerStyle} /> : null}
          {layout.strobes[bodyIndex].map((_, copy) =>
            marker("simulation-strobe", `strobe-marker-${bodyIndex}-${copy}`),
          )}
          {spec.arrows.map((arrow) => (
            <View
              key={`${bodyIndex}-${arrow}`}
              testID={`simulation-arrow-${arrow}`}
              style={markerStyle}
            />
          ))}
        </View>
      ))}
      {layout.vectors.map((vector, index) => (
        <View
          key={`vector-marker-${index}`}
          testID={`simulation-vector-${vector.vector.role}`}
          style={markerStyle}
        >
          {vector.label ? <View testID="simulation-vector-label" style={markerStyle} /> : null}
          {vector.body !== null ? marker("simulation-vector-attached") : null}
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
