import {
  collapseAdjacentMoleculeFences,
  parseMoleculeFence,
} from "@/lib/moleculePair";

const SDF = `Ethanol
     RDKit          3D

  3  2  0  0  0  0  0  0  0  0999 V2000
    0.0000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0  0
    1.5000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0  0
    2.5000    1.0000    0.0000 O   0  0  0  0  0  0  0  0  0  0  0  0  0
  1  2  1  0
  2  3  1  0
M  END`;

describe("collapseAdjacentMoleculeFences", () => {
  it("replaces a closed smiles + molecule3d pair with one molecule fence", () => {
    const input = "```smiles\nCCO\n```\n\n```molecule3d\n" + SDF + "\n```";
    const out = collapseAdjacentMoleculeFences(input);
    expect(out).toContain("```molecule\n");
    expect(out).not.toContain("```smiles");
    expect(out).not.toContain("```molecule3d");
    const match = /```molecule\n([\s\S]*?)\n```/.exec(out);
    expect(match).not.toBeNull();
    expect(parseMoleculeFence(match![1]!)).toEqual({
      smiles: "CCO",
      caption: null,
      sdf: SDF,
    });
  });

  it("pairs chemistry lang the same way and keeps a SMILES caption", () => {
    const input = "```chemistry\nEthanol\nCCO\n```\n```molecule3d\n" + SDF + "\n```";
    const out = collapseAdjacentMoleculeFences(input);
    const body = out.replace(/^```molecule\n/, "").replace(/\n```$/, "");
    expect(parseMoleculeFence(body)).toEqual({
      smiles: "CCO",
      caption: "Ethanol",
      sdf: SDF,
    });
  });

  it("leaves smiles-only, molecule3d-only, and prose-separated pairs alone", () => {
    expect(collapseAdjacentMoleculeFences("```smiles\nCCO\n```")).toContain("```smiles");
    expect(collapseAdjacentMoleculeFences("```molecule3d\n" + SDF + "\n```")).toContain(
      "```molecule3d",
    );
    const split =
      "```smiles\nCCO\n```\n\nSee the 3D view:\n\n```molecule3d\n" + SDF + "\n```";
    expect(collapseAdjacentMoleculeFences(split)).toBe(split);
  });

  it("does not collapse while the 3D fence is still open (streaming)", () => {
    const input = "```smiles\nCCO\n```\n\n```molecule3d\nEthanol\n     RDKit";
    expect(collapseAdjacentMoleculeFences(input)).toBe(input);
  });
});

describe("parseMoleculeFence", () => {
  it("reads JSON smiles/caption/sdf", () => {
    expect(
      parseMoleculeFence(JSON.stringify({ smiles: "CCO", caption: "Ethanol", sdf: SDF })),
    ).toEqual({ smiles: "CCO", caption: "Ethanol", sdf: SDF });
  });

  it("falls back to a chemistry SMILES body", () => {
    expect(parseMoleculeFence("Ethanol\nCCO")).toEqual({
      smiles: "CCO",
      caption: "Ethanol",
      sdf: null,
    });
  });

  it("returns null for empty or non-SMILES JSON", () => {
    expect(parseMoleculeFence("")).toBeNull();
    expect(parseMoleculeFence(JSON.stringify({ sdf: SDF }))).toBeNull();
  });
});
