/**
 * The scene's angle arcs and stated vectors, drawn all at once or, in a scene
 * the server built in stages (`sceneStages`), each on its turn: an arrow grows
 * from its anchor to its tip, and what belongs to it fades in once it is whole.
 */
import { type ReactNode } from "react";
import { Group, Skia } from "@shopify/react-native-skia";
import { useDerivedValue, type SharedValue } from "react-native-reanimated";

import {
  arrowHeadSize,
  stageGrowth,
  stageReveal,
  type SceneLayout,
  type SceneStages,
  type ScreenPoint,
  type VectorLayout,
} from "@/lib/physics/simulation";
import type { Theme } from "@/lib/theme";
import { appendArrowHead, arrowPath } from "@/components/rich/skia/paths";
import { AngleArc } from "@/components/rich/simulation/parts";
import {
  RidingVector,
  StatedVector,
  VectorMarks,
  vectorPaint,
  type Wheel,
} from "@/components/rich/simulation/vectors";

type Turn = { progress: SharedValue<number>; turn: number; count: number };

/** Its children, faded in once the arrows of `turn` are whole. */
function StagedReveal({ progress, turn, count, children }: Turn & { children: ReactNode }) {
  const opacity = useDerivedValue(() => stageReveal(progress.value, turn, count));
  return <Group opacity={opacity}>{children}</Group>;
}

/** `node` as it is, or held back for its turn when the scene is staged and it has one. */
export function onItsTurn(
  node: ReactNode,
  key: string,
  progress: SharedValue<number>,
  stages: SceneStages | null,
  turn: number | null | undefined,
): ReactNode {
  if (!stages || turn === null || turn === undefined) return node;
  return (
    <StagedReveal key={key} progress={progress} turn={turn} count={stages.count}>
      {node}
    </StagedReveal>
  );
}

/**
 * A stated vector growing on its turn, along the line the layout fitted. Whole,
 * it is the arrow `StatedVector` draws; a still scene's riding vector sits
 * where its body does, so it grows the same way.
 */
function StagedVector({
  layout,
  theme,
  progress,
  turn,
  count,
}: Turn & { layout: VectorLayout; theme: Theme }) {
  const paint = vectorPaint(layout.vector.role, theme);
  const { stroke } = paint;
  const from: ScreenPoint = layout.from;
  const full = Math.hypot(layout.tip.px - from.px, layout.tip.py - from.py);
  const ux = full > 0 ? (layout.tip.px - from.px) / full : 0;
  const uy = full > 0 ? (layout.tip.py - from.py) / full : 0;
  const fullHead = layout.head;
  const shaft = useDerivedValue(() => {
    const length = full * stageGrowth(progress.value, turn, count);
    if (!(length > 0)) return Skia.PathBuilder.Make().detach();
    const head = Math.min(fullHead, arrowHeadSize(length));
    if (stroke === "force") return arrowPath(from.px, from.py, ux, uy, length, head, "filled");
    const path = Skia.PathBuilder.Make();
    path.moveTo(from.px, from.py);
    path.lineTo(from.px + ux * length, from.py + uy * length);
    return path.detach();
  });
  const head = useDerivedValue(() => {
    const path = Skia.PathBuilder.Make();
    const length = full * stageGrowth(progress.value, turn, count);
    if (!(length > 0) || stroke === "force") return path.detach();
    return appendArrowHead(
      path,
      from.px + ux * length,
      from.py + uy * length,
      ux,
      uy,
      Math.min(fullHead, arrowHeadSize(length)),
      stroke === "motion" ? "open" : "ticks",
      length,
    ).detach();
  });
  return <VectorMarks {...paint} shaft={shaft} head={stroke === "force" ? shaft : head} />;
}

/** The angle arcs, then the stated vectors over them. */
export function SceneArrows({
  layout,
  stages,
  progress,
  wheel,
  theme,
  canvasWidth,
  canvasHeight,
}: {
  layout: SceneLayout;
  stages: SceneStages | null;
  progress: SharedValue<number>;
  wheel: Wheel;
  theme: Theme;
  canvasWidth: number;
  canvasHeight: number;
}) {
  return (
    <>
      {layout.angles.map((angle, index) =>
        onItsTurn(
          <AngleArc key={`angle-${index}`} layout={angle} theme={theme} />,
          `angle-${index}`,
          progress,
          stages,
          stages?.angles[index],
        ),
      )}
      {layout.vectors.map((vector, index) =>
        stages ? (
          <StagedVector
            key={`vector-${index}`}
            layout={vector}
            theme={theme}
            progress={progress}
            turn={stages.vectors[index]}
            count={stages.count}
          />
        ) : vector.body !== null ? (
          <RidingVector
            key={`vector-${index}`}
            layout={vector}
            track={layout.tracks[vector.body]}
            progress={progress}
            wheel={wheel}
            theme={theme}
            canvasWidth={canvasWidth}
            canvasHeight={canvasHeight}
          />
        ) : (
          <StatedVector key={`vector-${index}`} layout={vector} theme={theme} />
        ),
      )}
    </>
  );
}
