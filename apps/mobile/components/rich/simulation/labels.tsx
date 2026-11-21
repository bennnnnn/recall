/** The scene's labels, drawn last, each following what it names. */
import { type ReactNode } from "react";
import { Group, type SkFont } from "@shopify/react-native-skia";
import { useDerivedValue, type SharedValue } from "react-native-reanimated";

import {
  clampCanvasLabelBaseline,
  clampCanvasLabelX,
  derivedLabelOrigin,
  placeNudgedLabel,
  vectorLabelOrigin,
  type ArrowLabelLayout,
  type BodyLabelLayout,
  type PlacedLabel,
  type SceneLayout,
  type SceneStages,
  type ScreenPoint,
  type SimulationSpec,
  type VectorLayout,
} from "@/lib/physics/simulation";
import { trajectoryPointAt } from "@/lib/math/trajectory";
import { Theme, withAlpha } from "@/lib/theme";
import { HaloText } from "@/components/rich/skia/HaloText";
import { onItsTurn } from "@/components/rich/simulation/sceneArrows";
import {
  arrowNow,
  ridingNow,
  vectorColor,
  type ArrowContext,
  type Slope,
  type Wheel,
} from "@/components/rich/simulation/vectors";

export const LABEL_FONT_SIZE = 11;

/** The planet's muted disc, as one opaque colour so its label's halo can match it. */
export function planetFill(theme: Theme): string {
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
  // eslint-disable-next-line no-restricted-syntax -- builds one opaque colour from two theme colours, as withAlpha builds a tint
  return `rgb(${mixed[0]}, ${mixed[1]}, ${mixed[2]})`;
}

/** Where a moving label sits this frame, and whether it shows (1) or hides with its arrow (0). */
type LabelSpot = { x: number; y: number; shown: number };

/** A label that follows an arrow: placed from `spot` every frame, hidden while it is. */
function MovingLabel({
  spot,
  text,
  font,
  fallbacks,
  color,
  theme,
}: {
  spot: SharedValue<LabelSpot>;
  text: string;
  font: SkFont | null;
  fallbacks: readonly (SkFont | null)[];
  color: string;
  theme: Theme;
}) {
  const x = useDerivedValue(() => spot.value.x);
  const y = useDerivedValue(() => spot.value.y);
  const opacity = useDerivedValue(() => spot.value.shown);
  return (
    <Group opacity={opacity}>
      <HaloText
        x={x}
        y={y}
        text={text}
        font={font}
        fallbacks={fallbacks}
        color={color}
        halo={theme.bg}
      />
    </Group>
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
  font: SkFont | null;
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
  return (
    <MovingLabel
      spot={spot}
      text={layout.vector.label ?? ""}
      font={font}
      fallbacks={fallbacks}
      color={vectorColor(layout.vector.role, theme)}
      theme={theme}
    />
  );
}

/** Every label in the scene, drawn over every line. */
export function SceneLabels({
  spec,
  layout,
  font,
  fallbacks,
  wheel,
  theme,
  progress,
  stages,
  centre,
  slope,
  canvasWidth,
  canvasHeight,
}: {
  spec: SimulationSpec;
  layout: SceneLayout;
  font: SkFont | null;
  fallbacks: readonly (SkFont | null)[];
  wheel: Wheel;
  theme: Theme;
  progress: SharedValue<number>;
  /** A scene built in stages: each label of an arrow or arc shows once it is drawn. */
  stages: SceneStages | null;
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
      <StatedLabels
        layout={layout}
        stages={stages}
        progress={progress}
        fixedLabel={fixedLabel}
        font={font}
        fallbacks={fallbacks}
        wheel={wheel}
        theme={theme}
        canvasWidth={canvasWidth}
        canvasHeight={canvasHeight}
      />
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

type FixedLabel = (label: PlacedLabel, key: string, color: string) => ReactNode;

/** The angles' and stated vectors' labels, each on its turn in a staged scene. */
function StatedLabels({
  layout,
  stages,
  progress,
  fixedLabel,
  font,
  fallbacks,
  wheel,
  theme,
  canvasWidth,
  canvasHeight,
}: {
  layout: SceneLayout;
  stages: SceneStages | null;
  progress: SharedValue<number>;
  fixedLabel: FixedLabel;
  font: SkFont | null;
  fallbacks: readonly (SkFont | null)[];
  wheel: Wheel;
  theme: Theme;
  canvasWidth: number;
  canvasHeight: number;
}) {
  return (
    <>
      {layout.angles.map((angle, index) => {
        if (!angle.label) return null;
        const key = `angle-label-${index}`;
        const color = angle.angle.role === "result" ? theme.primary : theme.textSecondary;
        return onItsTurn(
          fixedLabel(angle.label, key, color),
          key,
          progress,
          stages,
          stages?.angles[index],
        );
      })}
      {layout.vectors.map((vector, index) => {
        if (!vector.label) return null;
        const key = `vector-label-${index}`;
        const label =
          vector.body !== null ? (
            <RidingVectorLabel
              key={key}
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
            fixedLabel(vector.label, key, vectorColor(vector.vector.role, theme))
          );
        return onItsTurn(label, key, progress, stages, stages?.vectors[index]);
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
  font: SkFont | null;
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
  return (
    <MovingLabel
      spot={spot}
      text={label.text}
      font={font}
      fallbacks={fallbacks}
      color={color}
      theme={theme}
    />
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
  font: SkFont | null;
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
