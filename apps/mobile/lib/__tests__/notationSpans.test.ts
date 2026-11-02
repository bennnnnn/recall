import { codeNotation } from "@/lib/markdown/notationSpans";

describe("codeNotation", () => {
  it("codes a SMILES string and leaves prose alone", () => {
    expect(codeNotation("Caffeine is CN1C=NC2=C1C(=O)N(C(=O)N2C)C.")).toBe(
      "Caffeine is `CN1C=NC2=C1C(=O)N(C(=O)N2C)C`.",
    );
    expect(codeNotation("Acetyl chloride is ClC(Br)=O here")).toBe(
      "Acetyl chloride is `ClC(Br)=O` here",
    );
    expect(codeNotation("F=ma(t) holds")).toBe("F=ma(t) holds");
  });

  // CodeQL js/redos: "B" then "b" as well as "Bb" read each pair two ways, so a long run
  // of "Bb" ending in a letter no atom has took exponential time (44 letters: 0.3 s, doubling every
  // two more).
  it("reads a long run of letters once", () => {
    const token = `C(=O)${"Bb".repeat(20_000)}z`;
    const started = Date.now();
    expect(codeNotation(`see ${token}`)).toBe(`see ${token}`);
    expect(Date.now() - started).toBeLessThan(1000);
  });

  it("trims a token's trailing punctuation in one pass", () => {
    const dots = `${".".repeat(50_000)}x(=`;
    const started = Date.now();
    expect(codeNotation(dots)).toBe(dots);
    expect(codeNotation("Ethene is C=C(C)C.")).toBe("Ethene is `C=C(C)C`.");
    expect(Date.now() - started).toBeLessThan(1000);
  });
});
