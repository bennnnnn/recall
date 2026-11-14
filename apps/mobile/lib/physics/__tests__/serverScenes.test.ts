/**
 * Every ```simulation scene in `docs/fixtures/simulation_scenes.json` is one the server wrote
 * (`apps/api/app/tests/services/test_simulation_scene_fixture.py` holds the dump to the
 * server's schema and to every scene type its solver draws). The phone's other scene tests
 * use hand-written specs; these are the real ones, read the way the app reads a fence:
 * a circuit, a ray diagram or a wave by its diagram reader, a body scene by the simulation
 * parser (GFX-04, 2026-11-13 STEM audit).
 */
import { parsePhysicsDiagram } from "@/components/rich/diagrams/spec";
import { diagramKind } from "@/lib/physics/diagramKind";
import { parseSimulationSpec } from "@/lib/physics/simulation/parse";
import { simulationAccessibilityLabel } from "@/lib/physics/simulation/describe";

import fixture from "../../../../../docs/fixtures/simulation_scenes.json";

type Scene = { question: string; type: string; fence: string };

const scenes: Scene[] = fixture.scenes;
const OPEN = "```simulation\n";
const body = (fence: string) => fence.slice(OPEN.length, fence.lastIndexOf("\n```"));
const t = (key: string) => key;

describe("server-written simulation scenes", () => {
  it("is a dump of real scenes of every kind the phone draws", () => {
    expect(scenes.length).toBeGreaterThan(50);
    const types = new Set(scenes.map((scene) => scene.type));
    for (const kind of ["circuit", "rays", "wave", "projectile_motion", "free_body"]) {
      expect(types).toContain(kind);
    }
  });

  it.each(scenes.map((scene, index) => [index, scene.type, scene] as const))(
    "scene %i (%s) parses as the app reads it",
    (_index, type, scene) => {
      expect(scene.fence.startsWith(OPEN)).toBe(true);
      const raw = body(scene.fence);
      const kind = diagramKind(raw);
      if (kind) {
        expect(kind).toBe(type);
        expect(parsePhysicsDiagram(raw, kind)).not.toBeNull();
        return;
      }
      const spec = parseSimulationSpec(raw);
      expect(spec).not.toBeNull();
      expect(simulationAccessibilityLabel(spec!, t).trim()).not.toBe("");
    },
  );
});
