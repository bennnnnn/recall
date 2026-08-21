import { parseMolecule3DFence } from "@/lib/molecule3dFence";

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
    // First non-empty line before counts is the program line.
    expect(result!.caption).toBe("RDKit          3D");
  });

  it("returns null when there is no M  END", () => {
    const result = parseMolecule3DFence("just some text without an SDF block");
    expect(result).toBeNull();
  });

  it("returns null for empty content", () => {
    expect(parseMolecule3DFence("")).toBeNull();
    expect(parseMolecule3DFence("   ")).toBeNull();
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
