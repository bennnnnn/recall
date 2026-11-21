/**
 * A moving body's faint copies at evenly spaced samples, so a still frame shows the motion
 * too: the widening gaps of a fall. Drawn where the scene draws them, under the live bodies.
 */
import type { SceneLayout, SimulationSpec } from "@/lib/physics/simulation";
import { BodyShape } from "@/components/rich/simulation/parts";

/** How strongly a strobe copy shows: enough to read the spacing, never a second body. */
const STROBE_OPACITY = 0.28;

export function StrobeCopies({
  spec,
  layout,
  bodyColor,
}: {
  spec: SimulationSpec;
  layout: SceneLayout;
  bodyColor: (role: "primary" | "secondary") => string;
}) {
  return (
    <>
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
    </>
  );
}
