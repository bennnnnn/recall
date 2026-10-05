import {
  PHYSICS_CONSTANTS,
  PHYSICS_FORMULAS,
  PHYSICS_FORMULA_COUNT,
  PHYSICS_TOPICS,
  physicsConstantEquation,
  searchPhysicsConstants,
  searchPhysicsFormulas,
} from "../formulaReference";
import { layoutMath } from "@/lib/math/layout";
import { parseSimpleLatex } from "@/lib/math/text";

describe("physics formula reference", () => {
  it("contains the requested 43 topics and 541 formula entries", () => {
    expect(PHYSICS_TOPICS).toHaveLength(43);
    expect(PHYSICS_FORMULAS).toHaveLength(PHYSICS_FORMULA_COUNT);
    expect(new Set(PHYSICS_FORMULAS.map(({ id }) => id)).size).toBe(PHYSICS_FORMULA_COUNT);
    expect(
      new Set(PHYSICS_FORMULAS.map(({ name, equation }) => `${name}|${equation}`)).size,
    ).toBe(PHYSICS_FORMULA_COUNT);
    expect(new Set(PHYSICS_TOPICS.map(({ id }) => id)).size).toBe(43);
    expect(PHYSICS_TOPICS.every(({ id }) => PHYSICS_FORMULAS.some((row) => row.topicId === id))).toBe(true);
    expect(PHYSICS_FORMULAS.every((row) => PHYSICS_TOPICS.some((topic) => topic.id === row.topicId))).toBe(true);
    expect(PHYSICS_FORMULAS.every((formula) => formula.equation.trim().length > 0)).toBe(true);
    expect(PHYSICS_FORMULAS.every((formula) => formula.name.trim().length > 0)).toBe(true);
  });

  it("has all three levels and exactly 32 constants", () => {
    expect(new Set(PHYSICS_FORMULAS.map(({ level }) => level))).toEqual(
      new Set(["middle_school", "high_school", "undergraduate"]),
    );
    expect(PHYSICS_CONSTANTS).toHaveLength(32);
    expect(new Set(PHYSICS_CONSTANTS.map(({ id }) => id)).size).toBe(32);
  });

  it("includes the readable core equations from the pasted reference", () => {
    const sourceRows = [
      "Lever balance",
      "Ideal wheel-and-axle advantage",
      "Ideal gear advantage",
      "Ideal screw advantage",
      "Ideal wedge advantage",
      "Standard atmospheric pressure near sea level",
      "Speed of sound in air at 20 °C",
      "Speed of light in vacuum",
      "Light-year conversion",
      "Energy cost",
      "Cells in series",
    ];
    const names = new Set(PHYSICS_FORMULAS.map(({ name }) => name));
    for (const name of sourceRows) expect(names.has(name)).toBe(true);
  });

  it("parses and lays out every equation with the mobile math renderer", () => {
    for (const formula of PHYSICS_FORMULAS) {
      const segments = parseSimpleLatex(formula.equation);
      const layout = layoutMath(segments, 18);
      expect(segments.length).toBeGreaterThan(0);
      expect(Number.isFinite(layout.width)).toBe(true);
      expect(Number.isFinite(layout.height)).toBe(true);
      expect(layout.width).toBeGreaterThan(0);
      expect(layout.height).toBeGreaterThan(0);
    }
  });

  it("converts and lays out every constant, including scientific-notation values", () => {
    for (const constant of PHYSICS_CONSTANTS) {
      const equation = physicsConstantEquation(constant);
      const segments = parseSimpleLatex(equation);
      const layout = layoutMath(segments, 18);
      expect(equation).not.toContain("× 10");
      expect(Number.isFinite(layout.width) && layout.width > 0).toBe(true);
      expect(Number.isFinite(layout.height) && layout.height > 0).toBe(true);
    }
  });

  it("searches across equation names, symbols, and topic names", () => {
    expect(searchPhysicsFormulas("Coulomb", "all", "all").map(({ id }) => id)).toContain(
      "electrostatics-2",
    );
    expect(searchPhysicsFormulas("wavelength", "all", "all").length).toBeGreaterThan(0);
    expect(searchPhysicsFormulas("λ", "all", "all").length).toBeGreaterThan(0);
    expect(searchPhysicsFormulas("\\lambda", "all", "all").length).toBeGreaterThan(0);
    expect(searchPhysicsFormulas("fluids", "all", "all").length).toBeGreaterThan(0);
  });

  it("searches constants by names and LaTeX or Unicode Greek symbols", () => {
    expect(searchPhysicsConstants("electron mass").map(({ id }) => id)).toContain("electron-mass");
    expect(searchPhysicsConstants("\\epsilon_0").map(({ id }) => id)).toContain("epsilon0");
    expect(searchPhysicsConstants("μ").map(({ id }) => id)).toContain("mu0");
  });

  it("combines level, topic, and keyword filters", () => {
    const results = searchPhysicsFormulas("energy", "undergraduate", "thermodynamics");
    expect(results.length).toBeGreaterThan(0);
    expect(results.every((formula) => formula.topicId === "thermodynamics")).toBe(true);
    expect(results.every((formula) => formula.level === "undergraduate")).toBe(true);
    expect(searchPhysicsFormulas("", "middle_school", "thermodynamics")).toHaveLength(0);
  });
});
