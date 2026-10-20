/**
 * Parsing and geometry for the `simulation` fence.
 *
 * Split out of the component for the same reason `trajectory.ts` was: these are
 * plain functions the `lib` jest project can assert directly, and the ones the
 * renderer calls per frame carry the `"worklet"` directive so they can run on
 * the UI thread.
 *
 * Nothing here does physics. The server sends every body as a sampled path in
 * world units and the index is the clock, exactly as the trajectory graph
 * does — this package only maps those samples onto the screen and reads
 * directions off them.
 */
export {
  SCENE_TITLE_KEYS,
  type SimulationArrow,
  type SimulationKind,
  type SimulationSpec,
} from "@/lib/physics/simulation/spec";
export { parseSimulationSpec } from "@/lib/physics/simulation/parse";
export {
  describeSimulation,
  sceneTitle,
  simulationAccessibilityLabel,
} from "@/lib/physics/simulation/describe";
export {
  clampCanvasLabelBaseline,
  clampCanvasLabelX,
  FLUID_TINT,
  projectPath,
  SIMULATION_HEIGHT,
  SIMULATION_MIN_HEIGHT,
  SIMULATION_PAD,
  simulationTransform,
  simulationViewportHeight,
  worldToScreen,
  type ScreenPoint,
} from "@/lib/physics/simulation/viewport";
export {
  isClosedPath,
  maxTrackSpeed,
  simulationIsAnimated,
  strobeIndices,
  tangentAt,
} from "@/lib/physics/simulation/paths";
export {
  ARROW_EDGE_INSET,
  ARROW_MAX_LENGTH,
  ARROW_MIN_LENGTH,
  arrowHeadSize,
  bodyBoxAngle,
  bodyEdgeDistance,
  bodyExtent,
  clipArrowAtCircle,
  clipArrowLength,
  derivedArrowGeometry,
  fitArrowLength,
  leverLoadAnchor,
  MIN_CLIPPED_ARROW,
  PIVOT_SIZE,
  riddenVectorGeometry,
  vectorScreenLengths,
  vectorStroke,
  velocityArrowLength,
  VELOCITY_MIN_LENGTH,
} from "@/lib/physics/simulation/arrows";
export {
  bodyLabelOffset,
  clearanceAlong,
  derivedLabelOrigin,
  placeNudgedLabel,
  segmentHitsBox,
  tipLabelOrigin,
  vectorLabelOrigin,
  type LabelBox,
  type PlacedLabel,
} from "@/lib/physics/simulation/labels";
export {
  ANGLE_MAX_RADIUS,
  ANGLE_RADIUS,
  angleArcPoints,
  angleArrowHead,
  angleLabelBox,
  angleRadius,
  onPulleyRim,
  pulleyRope,
  supportGeometry,
  tetherEnd,
  type SupportLayout,
} from "@/lib/physics/simulation/parts";
export { inclineDirections, inclineSurface, inclineWedge } from "@/lib/physics/simulation/incline";
export { layoutSimulationScene, type SceneLayout } from "@/lib/physics/simulation/layout";
export {
  type AngleLayout,
} from "@/lib/physics/simulation/layoutShapes";
export {
  type BodyLabelLayout,
  type SolidLayout,
} from "@/lib/physics/simulation/layoutLabels";
export {
  type ArrowLabelLayout,
  type VectorLayout,
} from "@/lib/physics/simulation/layoutNudgedLabels";
