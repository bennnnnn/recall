import { parseMolGeometry, parseMolecule3DFence } from "@/lib/molecule3dFence";

const VALID_SDF = `Ethanol
     RDKit          3D

  3  2  0  0  0  0  0  0  0  0999 V2000
    0.0000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0  0
    1.5000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0  0
    2.5000    1.0000    0.0000 O   0  0  0  0  0  0  0  0  0  0  0  0  0
  1  2  1  0
  2  3  1  0
M  END`;

describe("parseMolecule3DFence", () => {
  it("parses a valid SDF block with M  END", () => {
    const result = parseMolecule3DFence(VALID_SDF);
    expect(result).not.toBeNull();
    expect(result!.sdf).toContain("M  END");
    expect(result!.sdf).toContain("V2000");
    expect(result!.caption).toBe("Ethanol");
  });

  it("parses an SDF block with only program line (caption from first non-empty line)", () => {
    const sdf = `
     RDKit          3D

  3  2  0  0  0  0  0  0  0  0999 V2000
    0.0000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0  0
    1.5000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0  0
    2.5000    1.0000    0.0000 O   0  0  0  0  0  0  0  0  0  0  0  0  0
  1  2  1  0
  2  3  1  0
M  END`;
    const result = parseMolecule3DFence(sdf);
    expect(result).not.toBeNull();
    expect(result!.sdf).toContain("M  END");
    // Program/timestamp line is not a user-facing caption.
    expect(result!.caption).toBeNull();
  });

  it("returns null when there is no M  END", () => {
    const result = parseMolecule3DFence("just some text without an SDF block");
    expect(result).toBeNull();
  });

  it("returns null for empty content", () => {
    expect(parseMolecule3DFence("")).toBeNull();
    expect(parseMolecule3DFence("   ")).toBeNull();
  });

  it("strips a prepended formula caption so the MOL header stays 3 lines", () => {
    // Production fences were ```molecule3d\nO2\n<RDKit molblock>``` — that extra
    // line shifted the V2000 counts off line 4 and 3Dmol.js drew nothing.
    const sdf = `O2

     RDKit          3D

  2  1  0  0  0  0  0  0  0  0999 V2000
    0.5705    0.0000    0.0000 O   0  0  0  0  0  0
   -0.5705    0.0000    0.0000 O   0  0  0  0  0  0
  1  2  2  0
M  END`;
    const result = parseMolecule3DFence(sdf);
    expect(result).not.toBeNull();
    expect(result!.caption).toBe("O2");
    const mol = result!.sdf;
    const lines = mol.split("\n");
    const countsIdx = lines.findIndex((line) => /V2000/.test(line));
    expect(countsIdx).toBe(3);
    expect(mol).toContain("$$$$");
  });

  it("reads a caption after M  END", () => {
    const sdf = `
     RDKit          3D

  2  1  0  0  0  0  0  0  0  0999 V2000
    0.5705    0.0000    0.0000 O   0  0  0  0  0  0
   -0.5705    0.0000    0.0000 O   0  0  0  0  0  0
  1  2  2  0
M  END
O2`;
    const result = parseMolecule3DFence(sdf);
    expect(result!.caption).toBe("O2");
  });

  it("handles V3000 counts line", () => {
    const sdf = `Aspirin
     RDKit          3D

  0  0  0  0  0  0  0  0  0  0999 V3000
M  V30 BEGIN CTAB
M  V30 COUNT 9 9
M  V30 END CTAB
M  END`;
    const result = parseMolecule3DFence(sdf);
    expect(result).not.toBeNull();
    expect(result!.sdf).toContain("M  END");
    expect(result!.caption).toBe("Aspirin");
  });
});

describe("parseMolGeometry", () => {
  it("reads O2 atoms and the double bond", () => {
    const sdf = `
     RDKit          3D

  2  1  0  0  0  0  0  0  0  0999 V2000
    0.5705    0.0000    0.0000 O   0  0  0  0  0  0
   -0.5705    0.0000    0.0000 O   0  0  0  0  0  0
  1  2  2  0
M  END
$$$$`;
    const geom = parseMolGeometry(sdf);
    expect(geom).not.toBeNull();
    expect(geom!.atoms).toHaveLength(2);
    expect(geom!.atoms.map((a) => a.el)).toEqual(["O", "O"]);
    expect(geom!.bonds).toEqual([{ a: 0, b: 1, order: 2 }]);
  });

  it("reads ethanol from parseMolecule3DFence output", () => {
    const parsed = parseMolecule3DFence(VALID_SDF);
    const geom = parseMolGeometry(parsed!.sdf);
    expect(geom!.atoms.map((a) => a.el)).toEqual(["C", "C", "O"]);
    expect(geom!.bonds).toHaveLength(2);
  });
});
