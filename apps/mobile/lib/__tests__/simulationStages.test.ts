/**
 * A still scene built in stages: the server numbers its arrows, the phone
 * draws them in that order. Parsing is as strict as the server's model; the
 * clock is asserted as plain functions, and
 * `components/__tests__/SimulationBlockStages.test.tsx` covers the render.
 */
import {
  parseSimulationSpec,
  sceneStages,
  stagedDuration,
  stageGrowth,
  stageReveal,
  type SimulationSpec,
} from "@/lib/physics/simulation";
import { RESOLVED } from "@/lib/__tests__/fixtures/stagedScenes";

function parse(spec: object): SimulationSpec | null {
  return parseSimulationSpec(JSON.stringify(spec));
}

function mustParse(spec: object): SimulationSpec {
  const parsed = parse(spec);
  if (!parsed) throw new Error("fixture did not parse");
  return parsed;
}

function withStage(stage: unknown) {
  return {
    ...RESOLVED,
    vectors: [{ ...RESOLVED.vectors[0], stage }, ...RESOLVED.vectors.slice(1)],
  };
}

describe("reading a staged scene", () => {
  it("keeps each vector's stage", () => {
    const scene = mustParse(RESOLVED);
    expect(scene.vectors.map((vector) => vector.stage)).toEqual([0, 1, 2]);
    expect(scene.titleKey).toBe("components");
  });

  it("reads a vector with no stage, or a null one, as it always did", () => {
    const { stage: _stage, ...plain } = RESOLVED.vectors[0];
    const scene = mustParse({ ...RESOLVED, vectors: [plain, { ...plain, stage: null }] });
    expect(scene.vectors.every((vector) => !("stage" in vector))).toBe(true);
  });

  it.each([
    ["a stage past 5", 6],
    ["a negative stage", -1],
    ["a fractional stage", 1.5],
    ["a stage written as text", "1"],
    ["a stage that is not a number", true],
  ])("refuses %s, as the server would", (_label, stage) => {
    expect(() => parse(withStage(stage))).not.toThrow();
    expect(parse(withStage(stage))).toBeNull();
  });

  it("accepts every stage up to 5", () => {
    for (const stage of [0, 1, 2, 3, 4, 5]) expect(parse(withStage(stage))).not.toBeNull();
  });

  it("keeps an arc's stage, and reads an arc with none as it always did", () => {
    expect(mustParse(RESOLVED).angles[0].stage).toBe(0);
    const { stage: _stage, ...plain } = RESOLVED.angles[0];
    const scene = mustParse({ ...RESOLVED, angles: [plain, { ...plain, stage: null }] });
    expect(scene.angles.every((angle) => !("stage" in angle))).toBe(true);
  });

  it.each([
    ["a stage past 5", 6],
    ["a negative stage", -1],
    ["a fractional stage", 0.5],
    ["a stage written as text", "0"],
  ])("refuses an arc with %s, as it refuses a vector's", (_label, stage) => {
    const bad = { ...RESOLVED, angles: [{ ...RESOLVED.angles[0], stage }] };
    expect(() => parse(bad)).not.toThrow();
    expect(parse(bad)).toBeNull();
  });
});

describe("sceneStages", () => {
  it("plays the server's stages in order, and a numbered arc with its own stage", () => {
    // The given 30° comes with the given vector, not with the component along its other edge.
    const stages = sceneStages(mustParse(RESOLVED));
    expect(stages).toEqual({ count: 3, vectors: [0, 1, 2], angles: [0] });
  });

  it("shows a numbered arc with that stage, wherever its edges run", () => {
    const scene = mustParse({ ...RESOLVED, angles: [{ ...RESOLVED.angles[0], stage: 2 }] });
    expect(sceneStages(scene)?.angles).toEqual([2]);
  });

  it("closes up an arc's stage with the arrows' stages", () => {
    const scene = mustParse({
      ...RESOLVED,
      vectors: [
        RESOLVED.vectors[0],
        { ...RESOLVED.vectors[1], stage: 3 },
        { ...RESOLVED.vectors[2], stage: 5 },
      ],
      angles: [{ ...RESOLVED.angles[0], stage: 3 }],
    });
    expect(sceneStages(scene)).toEqual({ count: 3, vectors: [0, 1, 2], angles: [1] });
  });

  it("shows an unnumbered arc with the latest arrow it runs along", () => {
    const { stage: _stage, ...unnumbered } = RESOLVED.angles[0];
    const scene = mustParse({ ...RESOLVED, angles: [unnumbered] });
    // Its edges run along the given vector (turn 0) and the horizontal component (turn 1).
    expect(sceneStages(scene)?.angles).toEqual([1]);
  });

  it("stages a scene whose only number is on an arc", () => {
    const scene = mustParse({
      ...RESOLVED,
      vectors: RESOLVED.vectors.map(({ stage: _stage, ...vector }) => vector),
      angles: [{ ...RESOLVED.angles[0], stage: 1 }],
    });
    expect(sceneStages(scene)).toEqual({ count: 2, vectors: [0, 0, 0], angles: [1] });
  });

  it("leaves a scene whose vectors and arcs carry no stage drawn all at once", () => {
    const plain = {
      ...RESOLVED,
      vectors: RESOLVED.vectors.map(({ stage: _stage, ...vector }) => vector),
      angles: RESOLVED.angles.map(({ stage: _stage, ...angle }) => angle),
    };
    expect(sceneStages(mustParse(plain))).toBeNull();
  });

  it("puts an unnumbered vector with stage 0 and closes up gaps between stages", () => {
    const { stage: _stage, ...first } = RESOLVED.vectors[0];
    const scene = mustParse({
      ...RESOLVED,
      vectors: [first, { ...RESOLVED.vectors[1], stage: 2 }, { ...RESOLVED.vectors[2], stage: 4 }],
    });
    expect(sceneStages(scene)?.vectors).toEqual([0, 1, 2]);
    expect(sceneStages(scene)?.count).toBe(3);
  });

  it("leaves an arc that runs along no arrow there from the start", () => {
    const scene = mustParse({
      ...RESOLVED,
      angles: [{ vertex: [5, 5], start_deg: 90, end_deg: 120, role: "given" }],
    });
    expect(sceneStages(scene)?.angles).toEqual([null]);
  });

  it("never stages a scene with a moving body: its clock is the motion", () => {
    const moving = {
      ...RESOLVED,
      type: "free_body",
      bodies: [{ radius: 0.4, role: "primary", path: [[0, 0], [1, 0], [2, 0]] }],
    };
    expect(sceneStages(mustParse(moving))).toBeNull();
  });

  it("gives each stage its grow and its pause", () => {
    // About 0.6–0.8 s of growing and a short rest, stage after stage.
    expect(stagedDuration(1)).toBeGreaterThanOrEqual(700);
    expect(stagedDuration(1)).toBeLessThanOrEqual(1200);
    expect(stagedDuration(3)).toBe(3 * stagedDuration(1));
  });
});

describe("the staged clock", () => {
  const COUNT = 3;

  it("grows no arrow of a later stage while an earlier one is still growing", () => {
    for (let step = 0; step <= 300; step += 1) {
      const progress = step / 300;
      for (let turn = 1; turn < COUNT; turn += 1) {
        if (stageGrowth(progress, turn, COUNT) > 0) {
          expect(stageGrowth(progress, turn - 1, COUNT)).toBe(1);
        }
      }
    }
  });

  it("grows each stage from nothing to whole, then holds it", () => {
    expect(stageGrowth(0, 0, COUNT)).toBe(0);
    expect(stageGrowth(0.1, 0, COUNT)).toBeGreaterThan(0);
    expect(stageGrowth(0.1, 0, COUNT)).toBeLessThan(1);
    expect(stageGrowth(0.1, 1, COUNT)).toBe(0);
    expect(stageGrowth(0.5, 1, COUNT)).toBeLessThan(1);
    expect(stageGrowth(0.6, 1, COUNT)).toBe(1);
    expect(stageGrowth(0.6, 2, COUNT)).toBe(0);
    expect([0, 1, 2].map((turn) => stageGrowth(1, turn, COUNT))).toEqual([1, 1, 1]);
  });

  it("shows a stage's labels only once its arrows are whole, and every one at the end", () => {
    for (let step = 0; step <= 300; step += 1) {
      const progress = step / 300;
      for (let turn = 0; turn < COUNT; turn += 1) {
        if (stageReveal(progress, turn, COUNT) > 0) {
          expect(stageGrowth(progress, turn, COUNT)).toBe(1);
        }
      }
    }
    expect([0, 1, 2].map((turn) => stageReveal(1, turn, COUNT))).toEqual([1, 1, 1]);
    expect(stageReveal(0, 0, COUNT)).toBe(0);
  });
});
