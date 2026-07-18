import { FRACTION_SLASH, unicodeFractionGlyph } from "@/lib/unicodeFraction";

describe("unicodeFractionGlyph", () => {
  it("returns precomposed vulgar fractions for common values", () => {
    expect(unicodeFractionGlyph("1", "2")).toBe("½");
    expect(unicodeFractionGlyph("1", "4")).toBe("¼");
    expect(unicodeFractionGlyph("3", "4")).toBe("¾");
    expect(unicodeFractionGlyph("2", "3")).toBe("⅔");
  });

  it("composes arbitrary digit fractions with FRACTION SLASH, not a box bar", () => {
    expect(unicodeFractionGlyph("11", "12")).toBe(`¹¹${FRACTION_SLASH}₁₂`);
    expect(unicodeFractionGlyph("11", "12")).not.toContain("─");
  });

  it("returns null for letter / mixed fractions so callers use plain solidus", () => {
    expect(unicodeFractionGlyph("m", "m")).toBeNull();
    expect(unicodeFractionGlyph("M", "2")).toBeNull();
    expect(unicodeFractionGlyph("1", "m")).toBeNull();
  });
});
