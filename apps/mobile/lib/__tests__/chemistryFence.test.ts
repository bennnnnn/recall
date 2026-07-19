import { parseChemistryFence } from "@/lib/chemistryFence";
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
