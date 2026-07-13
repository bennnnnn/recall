import { fixImplicitExponents, normalizeImplicitMathInProse } from "@/lib/normalizeImplicitMath";

describe("normalizeImplicitMath", () => {
  it("wraps parenthesized algebra from model output", () => {
    const input = "Given equation: ( x^2 + 2 = 6 )\nStep 2: ( x = \\pm \\sqrt{4} )";
    const out = normalizeImplicitMathInProse(input);
    expect(out).toContain("$x^2 + 2 = 6$");
    expect(out).toContain("$x = \\pm \\sqrt{4}$");
  });

  it("fixes implicit exponents and wraps bare equations", () => {
    const input = "Equation: x2+2=6\nx2=6-2\nx2=4";
    const out = normalizeImplicitMathInProse(input);
    expect(out).toContain("$x^2+2=6$");
    expect(out).toContain("$x^2=6-2$");
    expect(out).toContain("$x^2=4$");
  });

  it("fixes verification lines with squared digits", () => {
    const input = "For x=2: 22+2=4+2=6 ✓";
    const out = normalizeImplicitMathInProse(input);
    expect(out).toContain("$2^2+2=4+2=6$");
  });

  it("leaves normal prose alone", () => {
    const input = "Both solutions check out! (see step 2)";
    expect(normalizeImplicitMathInProse(input)).toBe(input);
  });

  it("unwraps dollar-wrapped bullet lines from model output", () => {
    const input = "$- Base = 8 cm$\n$- Height = 5 cm$";
    const out = normalizeImplicitMathInProse(input);
    expect(out).toBe("- Base = 8 cm\n- Height = 5 cm");
  });

  it("BUG FIX regression: does not swallow a bold-prefixed line into math delimiters", () => {
    // BARE_EQUATION_RE's char class allows `*` for multiplication, which also
    // matches markdown's `**bold**` markers — a line like "**Solve** 2^x + 5 = 7"
    // used to get misread as a bare equation and wrapped whole in `$...$`,
    // which renders as raw source text (not parsed markdown), showing the
    // literal `**` asterisks instead of bold.
    const input = "**Solve** 2^x + 5 = 7";
    expect(normalizeImplicitMathInProse(input)).toBe(input);
  });

  it("still wraps a genuine bare equation line with no markdown emphasis", () => {
    const input = "2^x = 7 - 5 = 2";
    expect(normalizeImplicitMathInProse(input)).toBe("$2^x = 7 - 5 = 2$");
  });

  it("skips fenced code blocks", () => {
    const { normalizeImplicitMath } = require("@/lib/normalizeImplicitMath");
    const input = "```python\n( x = 1 )\n```\nx2=4";
    const out = normalizeImplicitMath(input);
    expect(out).toContain("```python\n( x = 1 )\n```");
    expect(out).toContain("$x^2=4$");
  });
});

describe("fixImplicitExponents", () => {
  it("converts x2 to x^2", () => {
    expect(fixImplicitExponents("x2+2=6")).toBe("x^2+2=6");
  });
});
