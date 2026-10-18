import { bodyBoxAngle, bodyExtent } from "@/lib/physics/simulation/arrows";
import { type LabelBox } from "@/lib/physics/simulation/labels";
import {
  endsWhereItStarts,
  isClosedPath,
  maxTrackSpeed,
  samplePathAt,
  simulationIsAnimated,
} from "@/lib/physics/simulation/paths";
import { type SimulationSpec } from "@/lib/physics/simulation/spec";
import {
  projectPath,
  worldToScreen,
  type ScreenPoint,
  type SimulationTransform,
} from "@/lib/physics/simulation/viewport";

/** Progress values the label pass checks a moving scene at. */
const LAYOUT_FRAMES = 17;

/** The smallest a body is drawn, so a 2 cm ball is still a dot. */
const MIN_BODY_RADIUS = 4;

/**
 * What every stage of `layoutSimulationScene` reads: the scene on screen, and
 * where each body is at each frame the layout checks.
 */
export type SceneFrames = {
  spec: SimulationSpec;
  transform: SimulationTransform;
  width: number;
  height: number;
  measureText: (text: string) => number;
  fontSize: number;
  radii: number[];
  boxAngles: (number | null)[];
  extents: number[];
  tracks: ScreenPoint[][];
  closed: boolean[];
  maxSpeed: number;
  floorY: number | null;
  /** Each solid's rect on screen, fluids too. */
  solidBoxes: LabelBox[];
  obstacles: LabelBox[];
  centre: ScreenPoint | null;
  progresses: number[];
  /** Each body's centre at each sampled frame. */
  positions: ScreenPoint[][];
  /** How far each body has moved by each sampled frame. */
  shifts: { dx: number; dy: number }[][];
  pulleyCentre: ScreenPoint | null;
  pulleyRadius: number;
};

type SceneInput = Pick<
  SceneFrames,
  "spec" | "transform" | "width" | "height" | "measureText" | "fontSize"
>;

export function sceneFrames(input: SceneInput): SceneFrames {
  const { spec, transform } = input;
  const radii = spec.bodies.map((body) => Math.max(body.radius * transform.scale, MIN_BODY_RADIUS));
  const boxAngles = spec.bodies.map((body) => bodyBoxAngle(spec, body));
  const extents = radii.map((radius, index) => bodyExtent(radius, boxAngles[index]));
  const tracks = spec.bodies.map((body) => projectPath(body.path, transform));
  // A pendulum is sampled over whole swings, and turns round at the join, so
  // `isClosedPath` (which wants motion carrying straight on) never says so;
  // wrapping its window there is what gives the bob no velocity at full swing.
  const closed = tracks.map(
    (track) => isClosedPath(track) || (spec.type === "pendulum" && endsWhereItStarts(track)),
  );
  const maxSpeed = spec.arrows.includes("velocity")
    ? tracks.reduce((best, track, index) => Math.max(best, maxTrackSpeed(track, closed[index])), 0)
    : 0;
  const floorY = spec.ground ? worldToScreen(0, 0, transform).py : null;
  const solidBoxes = spec.solids.map((solid) => {
    const topLeft = worldToScreen(solid.rect.xMin, solid.rect.yMax, transform);
    const bottomRight = worldToScreen(solid.rect.xMax, solid.rect.yMin, transform);
    return {
      x: topLeft.px,
      y: topLeft.py,
      width: bottomRight.px - topLeft.px,
      height: bottomRight.py - topLeft.py,
    };
  });
  const obstacles = solidBoxes.filter((_, index) => spec.solids[index].kind === "solid");
  const centre = spec.centre ? worldToScreen(spec.centre.x, spec.centre.y, transform) : null;

  const animated = simulationIsAnimated(spec);
  const progresses = animated
    ? Array.from({ length: LAYOUT_FRAMES }, (_, i) => i / (LAYOUT_FRAMES - 1))
    : [0];
  const positions = tracks.map((track) =>
    progresses.map((progress) => samplePathAt(track, progress * (track.length - 1))),
  );
  const shifts = positions.map((frames) =>
    frames.map((point) => ({ dx: point.px - frames[0].px, dy: point.py - frames[0].py })),
  );

  const pulleyCentre = spec.pulley
    ? worldToScreen(spec.pulley.centre.x, spec.pulley.centre.y, transform)
    : null;
  const pulleyRadius = spec.pulley ? spec.pulley.radius * transform.scale : 0;

  return {
    ...input,
    radii,
    boxAngles,
    extents,
    tracks,
    closed,
    maxSpeed,
    floorY,
    solidBoxes,
    obstacles,
    centre,
    progresses,
    positions,
    shifts,
    pulleyCentre,
    pulleyRadius,
  };
}
