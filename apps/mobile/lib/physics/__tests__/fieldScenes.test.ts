/**
 * The electric field diagram, read and laid out from the fences the server
 * writes (`docs/fixtures/field_scenes.json`, held to the server by
 * `apps/api/app/tests/modules/physics/test_field_scene_fixture.py`), and
 * refused when a fence breaks the server's own rules.
 */
import { parsePhysicsDiagram, physicsDiagramCanvasHeight, type FieldDiagramSpec } from "@/components/rich/diagrams/spec";
import { diagramKind } from "@/lib/physics/diagramKind";
import { fieldTitle, layoutFieldScene, parseFieldSpec } from "@/lib/physics/field";
import { worldTransform, worldViewportHeight } from "@/lib/physics/optics";

import fixture from "../../../../../docs/fixtures/field_scenes.json";

type Scene = { question: string; fence: string };

const scenes: Scene[] = fixture.scenes;
const OPEN = "```simulation\n";
const body = (fence: string) => fence.slice(OPEN.length, fence.lastIndexOf("\n```"));
const WIDTH = 340;

function read(fence: string): FieldDiagramSpec {
  const raw = body(fence);
  expect(diagramKind(raw)).toBe("field");
  const spec = parsePhysicsDiagram(raw, "field");
  if (!spec || spec.kind !== "field") throw new Error("expected a field diagram");
  return spec;
}

describe("server-written field diagrams", () => {
  it("holds the owner's questions: single charges, a pair of each kind and plates", () => {
    expect(scenes.map((scene) => scene.question)).toEqual(
      expect.arrayContaining([
        "a positive charge",
        "a negative charge",
        "a positive and a negative charge",
        "two negative charges",
        "between two oppositely charged flat metal plates",
      ]),
    );
  });

  it.each(scenes.map((scene) => [scene.question, scene] as const))("%s parses and lays out", (_question, scene) => {
    const spec = read(scene.fence);
    const height = physicsDiagramCanvasHeight(spec, WIDTH);
    expect(height).toBe(worldViewportHeight(spec.bounds, WIDTH));
    const laid = layoutFieldScene(spec.field, spec.bounds, WIDTH, height);
    expect(laid.lines).toHaveLength(spec.field.lines.length);
    for (const line of laid.lines) {
      for (const point of line) {
        expect(point.px).toBeGreaterThanOrEqual(-1);
        expect(point.px).toBeLessThanOrEqual(WIDTH + 1);
        expect(point.py).toBeGreaterThanOrEqual(-1);
        expect(point.py).toBeLessThanOrEqual(height + 1);
      }
    }
    for (const arrow of laid.arrows) expect(Math.hypot(arrow.ux, arrow.uy)).toBeCloseTo(1, 5);
  });

  it("puts each charge where the server did, its radius at the picture's scale", () => {
    const spec = read(scenes.find((scene) => scene.question === "two negative charges")!.fence);
    const height = worldViewportHeight(spec.bounds, WIDTH);
    const t = worldTransform(spec.bounds, WIDTH, height);
    const laid = layoutFieldScene(spec.field, spec.bounds, WIDTH, height);
    expect(laid.charges.map((charge) => charge.sign)).toEqual([-1, -1]);
    expect(laid.charges[0].r).toBeCloseTo(spec.field.charges[0].radius * t.scale, 6);
    // The neutral point sits halfway between two equal charges.
    expect(laid.neutral).toHaveLength(1);
    expect(laid.neutral[0].px).toBeCloseTo((laid.charges[0].centre.px + laid.charges[1].centre.px) / 2, 1);
  });

  it("flips a direction's y for the screen", () => {
    const spec = read(scenes.find((scene) => scene.question.startsWith("between"))!.fence);
    const laid = layoutFieldScene(spec.field, spec.bounds, WIDTH, worldViewportHeight(spec.bounds, WIDTH));
    // The field runs down from the top plate: down the screen too.
    for (const arrow of laid.arrows) expect(arrow.uy).toBeGreaterThan(0.9);
    expect(laid.plates.map((plate) => plate.sign)).toEqual([1, -1]);
    expect(laid.plates[0].marks.length).toBeGreaterThanOrEqual(2);
  });

  it("titles a part's picture with its letter", () => {
    expect(fieldTitle("Electric Field", "a")).toBe("(a) Electric Field");
    expect(fieldTitle("Electric Field", undefined)).toBe("Electric Field");
  });
});

describe("parseFieldSpec refuses what the server never writes", () => {
  const line = [
    [0, 0],
    [1, 0],
  ];
  const charge = { at: [0, 0], sign: 1, radius: 0.16 };
  const plate = { start: [-1, 1], end: [1, 1], sign: 1 };
  it.each([
    ["no charges and no plates", { lines: [line] }],
    ["charges and plates", { charges: [charge], plates: [plate], lines: [line] }],
    ["no lines", { charges: [charge], lines: [] }],
    ["a line of one point", { charges: [charge], lines: [[[0, 0]]] }],
    ["a sign of two", { charges: [{ ...charge, sign: 2 }], lines: [line] }],
    ["a radius of nothing", { charges: [{ ...charge, radius: 0 }], lines: [line] }],
    ["an arrow with no direction", { charges: [charge], lines: [line], arrows: [{ at: [0, 0], dx: 0, dy: 0 }] }],
    ["a part that is no letter", { charges: [charge], lines: [line], part: "ab" }],
    ["four charges", { charges: [charge, charge, charge, charge], lines: [line] }],
    ["a plate of no length", { plates: [{ start: [0, 0], end: [0, 0], sign: 1 }], lines: [line] }],
  ])("%s", (_name, raw) => {
    expect(parseFieldSpec(raw)).toBeNull();
  });

  it("reads the smallest field a server writes", () => {
    expect(parseFieldSpec({ charges: [charge], lines: [line] })).toEqual({
      charges: [{ at: { x: 0, y: 0 }, sign: 1, radius: 0.16, label: undefined }],
      plates: [],
      lines: [
        [
          { x: 0, y: 0 },
          { x: 1, y: 0 },
        ],
      ],
      arrows: [],
      neutral: [],
      part: undefined,
    });
  });

  it("refuses a field fence that carries another diagram's object or a measure line", () => {
    const raw = JSON.parse(body(scenes[0].fence));
    expect(parsePhysicsDiagram(JSON.stringify({ ...raw, wave: { x: [0, 1], frames: [[0, 0], [0, 0]] } }), "field")).toBeNull();
    const measure = { anchor: [0, 0], dx: 1, dy: 0, role: "measure" };
    expect(parsePhysicsDiagram(JSON.stringify({ ...raw, vectors: [measure] }), "field")).toBeNull();
  });
});
