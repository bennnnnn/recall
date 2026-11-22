/**
 * A still scene built in stages: the server numbers its arrows (`stage`), and
 * the phone draws them in that order on one clock from 0 to 1. Resolving a
 * vector, the given arrow grows first, then its horizontal component, then
 * its vertical one. Nothing here decides an arrow; it only says when each of
 * the server's arrows is drawn, and how much of it.
 */
import { arcSitsOn } from "@/lib/physics/simulation/parts";
import { simulationIsAnimated } from "@/lib/physics/simulation/paths";
import { type SimulationSpec, type SimulationVector } from "@/lib/physics/simulation/spec";

/** How long one stage's arrows take to grow from anchor to tip, in ms. */
const STAGE_GROW_MS = 700;
/** The rest after each stage, while its labels and arcs fade in. */
const STAGE_PAUSE_MS = 300;

/** How far through its slot a stage's arrows are fully grown. */
const GROW_SHARE = STAGE_GROW_MS / (STAGE_GROW_MS + STAGE_PAUSE_MS);

export type SceneStages = {
  /** How many stages play, one after another. */
  count: number;
  /** Each vector's turn, 0 first: its stage's place among the stages the scene uses. */
  vectors: number[];
  /**
   * Each angle's turn: its own stage when the server numbered it, else the
   * latest of the arrows it measures, so its arc shows once both its edges are
   * drawn. Null for an unnumbered arc along no arrow, which is there from the
   * start like the rest of the scene.
   */
  angles: (number | null)[];
};

/**
 * The scene's stages, or null for a scene drawn all at once: one whose
 * vectors and arcs carry no stage, or one with a moving body, whose clock is its motion.
 * A vector with no stage goes with stage 0, and the stages close up, so a scene
 * numbered 0 and 2 plays two stages with no empty one between.
 */
export function sceneStages(spec: SimulationSpec): SceneStages | null {
  const numbered = [...spec.vectors, ...spec.angles].some((part) => part.stage !== undefined);
  if (!numbered || simulationIsAnimated(spec)) return null;
  const stageOf = (vector: SimulationVector) => vector.stage ?? 0;
  // An arc's own stage is numbered and closed up with the arrows' stages.
  const named = spec.angles.flatMap((angle) => (angle.stage === undefined ? [] : [angle.stage]));
  const used = [...new Set([...spec.vectors.map(stageOf), ...named])].sort((a, b) => a - b);
  const vectors = spec.vectors.map((vector) => used.indexOf(stageOf(vector)));
  const span = Math.max(spec.xMax - spec.xMin, spec.yMax - spec.yMin);
  const angles = spec.angles.map((angle) => {
    if (angle.stage !== undefined) return used.indexOf(angle.stage);
    const turns = spec.vectors.flatMap((vector, index) =>
      arcSitsOn(angle, vector, span) ? [vectors[index]] : [],
    );
    return turns.length > 0 ? Math.max(...turns) : null;
  });
  return { count: used.length, vectors, angles };
}

/** One pass of every stage, in ms. */
export function stagedDuration(count: number): number {
  return Math.max(1, count) * (STAGE_GROW_MS + STAGE_PAUSE_MS);
}

function clamp01(value: number): number {
  "worklet";
  return value < 0 ? 0 : value > 1 ? 1 : value;
}

/**
 * How much of an arrow is drawn at `progress`: 0 before its turn, growing
 * through its stage's first part, 1 from then on. Eased out, so it settles
 * onto its tip rather than stopping dead.
 */
export function stageGrowth(progress: number, turn: number, count: number): number {
  "worklet";
  const t = clamp01((progress * count - turn) / GROW_SHARE);
  return 1 - (1 - t) * (1 - t);
}

/** How strongly a stage's labels and arcs show: they fade in once its arrows are whole. */
export function stageReveal(progress: number, turn: number, count: number): number {
  "worklet";
  return clamp01((progress * count - turn - GROW_SHARE) / (1 - GROW_SHARE));
}
