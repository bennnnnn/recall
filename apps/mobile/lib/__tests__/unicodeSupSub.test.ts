import fixture from "@/../../docs/fixtures/script_glyphs.json";
import { normalizeUnicodeScripts, scriptGlyphBase, toSuperscript } from "@/lib/unicodeSupSub";

describe("toSuperscript", () => {
  it("maps digits and common letters to Unicode superscripts", () => {
    expect(toSuperscript("2")).toBe("²");
    expect(toSuperscript("x")).toBe("ˣ");
    expect(toSuperscript("n")).toBe("ⁿ");
    expect(toSuperscript("10")).toBe("¹⁰");
  });

  it("maps +/-/= and parens", () => {
    expect(toSuperscript("+")).toBe("⁺");
    expect(toSuperscript("-")).toBe("⁻");
    expect(toSuperscript("(2)")).toBe("⁽²⁾");
  });

  it("maps a slash fraction so 3^{2/3} is not baseline 32/3", () => {
    expect(toSuperscript("2/3")).toBe("²\u2044³");
    expect(toSuperscript("1/2")).toBe("¹\u2044²");
    expect(toSuperscript("2/q")).toBeNull();
  });

  it("returns null when any char lacks a Unicode superscript", () => {
    expect(toSuperscript("q")).toBeNull();
    expect(toSuperscript("C")).toBeNull();
    expect(toSuperscript("2,3")).toBeNull();
  });

  it("returns null for empty input", () => {
    expect(toSuperscript("")).toBeNull();
  });
});

describe("normalizeUnicodeScripts", () => {
  it("rewrites unicode superscript runs to caret LaTeX", () => {
    expect(normalizeUnicodeScripts("x²")).toBe("x^2");
    expect(normalizeUnicodeScripts("2¹⁰")).toBe("2^{10}");
    expect(normalizeUnicodeScripts("eˣ")).toBe("e^x");
  });

  it("rewrites unicode subscript runs to underscore LaTeX", () => {
    expect(normalizeUnicodeScripts("a₁₀")).toBe("a_{10}");
    expect(normalizeUnicodeScripts("xₙ")).toBe("x_n");
  });

  it("leaves ordinary ASCII math unchanged", () => {
    expect(normalizeUnicodeScripts("x^2 + y_1")).toBe("x^2 + y_1");
  });
});

describe("the server's script table", () => {
  const raised: Record<string, string> = fixture.superscript;
  const lowered: Record<string, string> = fixture.subscript;

  it("reads exactly the glyphs the server reads, each as its character", () => {
    // Every code point: a glyph the phone reads that the server does not would drift.
    for (let point = 0; point <= 0x10ffff; point += 1) {
      if (point >= 0xd800 && point <= 0xdfff) continue;
      const ch = String.fromCodePoint(point);
      const want =
        ch in raised
          ? { base: raised[ch], kind: "sup" }
          : ch in lowered
            ? { base: lowered[ch], kind: "sub" }
            : null;
      const read = scriptGlyphBase(ch);
      if (read === null && want === null) continue;
      expect([ch, read]).toEqual([ch, want]);
    }
  });

  it("never reads an ordinal indicator as a script", () => {
    for (const ch of Object.keys(fixture.not_scripts)) expect(scriptGlyphBase(ch)).toBeNull();
  });

  it("draws only glyphs that read back as their character", () => {
    for (const base of Object.values(raised)) {
      const drawn = toSuperscript(base);
      if (drawn !== null) expect(raised[drawn]).toBe(base);
    }
  });

  it("reads a raised run whole, as the server's caret", () => {
    expect(normalizeUnicodeScripts("e⁻ˣ")).toBe("e^{-x}");
    expect(normalizeUnicodeScripts("2ˣ⁺¹")).toBe("2^{x+1}");
    expect(normalizeUnicodeScripts("x\u{107A5}")).toBe("x^q");
    expect(normalizeUnicodeScripts("∫₀¹")).toBe("∫_0^1");
  });
});
