import {
  normalizeMoleculeFormulaToSmiles,
  parseChemistryFence,
  retagMoleculeMathToSmiles,
} from "@/lib/chemistryFence";
import { isStructuredFenceLang } from "@/lib/richBlocks";

describe("parseChemistryFence", () => {
  it("parses a bare SMILES line", () => {
    expect(parseChemistryFence("O=O")).toEqual({ smiles: "O=O", caption: null });
  });

  it("parses caption + SMILES", () => {
    expect(parseChemistryFence("Oxygen (O2)\nO=O")).toEqual({
      smiles: "O=O",
      caption: "Oxygen (O2)",
    });
  });

  it("parses nitrogen triple bond", () => {
    expect(parseChemistryFence("Nitrogen (N2)\nN#N")).toEqual({
      smiles: "N#N",
      caption: "Nitrogen (N2)",
    });
  });

  it("strips smiles: prefix", () => {
    expect(parseChemistryFence("smiles: CCO")).toEqual({
      smiles: "CCO",
      caption: null,
    });
  });

  it("returns null for empty content", () => {
    expect(parseChemistryFence("")).toBeNull();
    expect(parseChemistryFence("   \n  ")).toBeNull();
  });

  it("rejects oversized SMILES", () => {
    expect(parseChemistryFence("C".repeat(501))).toBeNull();
  });
});

describe("chemistry fence langs", () => {
  it("registers smiles and chemistry as structured langs", () => {
    expect(isStructuredFenceLang("smiles")).toBe(true);
    expect(isStructuredFenceLang("chemistry")).toBe(true);
  });
});

describe("normalizeMoleculeFormulaToSmiles", () => {
  it("accepts bonded structure formulas", () => {
    expect(normalizeMoleculeFormulaToSmiles("O=O")).toBe("O=O");
    expect(normalizeMoleculeFormulaToSmiles("N#N")).toBe("N#N");
    expect(normalizeMoleculeFormulaToSmiles("O=C=O")).toBe("O=C=O");
    expect(normalizeMoleculeFormulaToSmiles("N \\equiv N")).toBe("N#N");
    expect(normalizeMoleculeFormulaToSmiles("N ≡ N")).toBe("N#N");
    expect(normalizeMoleculeFormulaToSmiles("$O=O$")).toBe("O=O");
  });

  it("rejects real math", () => {
    expect(normalizeMoleculeFormulaToSmiles("E=mc^2")).toBeNull();
    expect(normalizeMoleculeFormulaToSmiles("x=2")).toBeNull();
    expect(normalizeMoleculeFormulaToSmiles("\\frac{1}{2}")).toBeNull();
    expect(normalizeMoleculeFormulaToSmiles("CO")).toBeNull();
  });
});

describe("retagMoleculeMathToSmiles", () => {
  it("retags math fence O=O to smiles", () => {
    const out = retagMoleculeMathToSmiles("```math\nO=O\n```");
    expect(out).toContain("```smiles");
    expect(out).toContain("O=O");
    expect(out).not.toContain("```math");
  });

  it("retags latex triple-bond nitrogen", () => {
    const out = retagMoleculeMathToSmiles("```math\nN \\equiv N\n```");
    expect(out).toBe("```smiles\nN#N\n```");
  });

  it("retags whole-line inline math", () => {
    const out = retagMoleculeMathToSmiles("Here is oxygen:\n\n$O=O$\n\nDone.");
    expect(out).toContain("```smiles\nO=O\n```");
    expect(out).not.toContain("$O=O$");
  });

  it("leaves algebra math alone", () => {
    const input = "```math\nE=mc^2\n```";
    expect(retagMoleculeMathToSmiles(input)).toBe(input);
  });

  it("preserves caption + formula math fences", () => {
    const out = retagMoleculeMathToSmiles("```math\nOxygen (O2)\nO=O\n```");
    expect(out).toBe("```smiles\nOxygen (O2)\nO=O\n```");
  });
});
