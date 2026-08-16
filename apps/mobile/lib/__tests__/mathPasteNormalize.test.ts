import {
  applyComposerTextChange,
  extractInsertedDelta,
  normalizePastedMath,
  PASTE_GROWTH_MIN,
  restoreCopiedFractions,
} from "@/lib/mathPasteNormalize";

describe("normalizePastedMath", () => {
  it("maps Unicode math glyphs to LaTeX and wraps $...$", () => {
    expect(normalizePastedMath("x² + y² = 1")).toBe("$x^2 + y^2 = 1$");
    expect(normalizePastedMath("½")).toBe("$\\frac{1}{2}$");
    expect(normalizePastedMath("√(x)")).toBe("$\\sqrt{x}$");
    expect(normalizePastedMath("a ≤ b ≠ c")).toBe("$a \\leq b \\neq c$");
    expect(normalizePastedMath("2 × π")).toBe("$2 \\times \\pi$");
  });

  it("leaves already-delimited math dollars in place", () => {
    expect(normalizePastedMath("$x^2$")).toBe("$x^2$");
  });

  it("rebuilds stacked fractions flattened by an HTML copy (MathPapa)", () => {
    // Live: copy 1/3 x = 1/4 x + -5 from a rendered page → composer got
    // "1 3 x = 1 4 x \\pm 5" (num/den split; + - smashed to \\pm).
    expect(normalizePastedMath("1 3 x = 1 4 x + -5")).toBe(
      "$\\frac{1}{3} x = \\frac{1}{4} x + -5$",
    );
    expect(
      normalizePastedMath("1\n3\nx = 1\n4\nx + -5"),
    ).toBe("$\\frac{1}{3} x = \\frac{1}{4} x + -5$");
    expect(normalizePastedMath("1/3 x = 1/4 x + -5")).toBe(
      "$\\frac{1}{3} x = \\frac{1}{4} x + -5$",
    );
  });

  it("does not rewrite non-math prose, bullets, or filenames", () => {
    expect(normalizePastedMath("* first\n* second")).toBe("* first\n* second");
    expect(normalizePastedMath("notes_draft.txt")).toBe("notes_draft.txt");
    expect(normalizePastedMath("**bold** text here")).toBe("**bold** text here");
    expect(normalizePastedMath("hello world")).toBe("hello world");
  });
});

describe("restoreCopiedFractions", () => {
  it("maps a flattened coefficient fraction to \\frac", () => {
    expect(restoreCopiedFractions("1 3 x")).toBe("\\frac{1}{3} x");
    expect(restoreCopiedFractions("1\n3 x")).toBe("\\frac{1}{3} x");
  });
  it("leaves slash fractions alone", () => {
    expect(restoreCopiedFractions("1/3 x")).toBe("1/3 x");
  });
});

describe("extractInsertedDelta / applyComposerTextChange", () => {
  it("ignores short typing bursts", () => {
    expect(extractInsertedDelta("ab", "abc")).toBeNull();
    expect("x".repeat(PASTE_GROWTH_MIN - 1).length).toBeLessThan(PASTE_GROWTH_MIN);
  });

  it("rewrites a short math paste, not only long ones", () => {
    expect(applyComposerTextChange("", "½")).toBe("$\\frac{1}{2}$");
    expect(applyComposerTextChange("", "x=4")).toBe("$x = 4$");
    expect(applyComposerTextChange("", "x²")).toBe("$x^2$");
  });

  it("keeps existing $ delimiters and formats the inside", () => {
    expect(applyComposerTextChange("", "$x=4$")).toBe("$x = 4$");
  });

  it("rewrites a pasted math delta in the middle of existing text", () => {
    const prev = "see ";
    const next = "see x² + 1";
    expect(applyComposerTextChange(prev, next)).toBe("see $x^2 + 1$");
  });

  it("does not wrap a long prose paste", () => {
    const prev = "";
    const next = "please read notes_draft.txt later";
    expect(applyComposerTextChange(prev, next)).toBe(next);
  });
});
