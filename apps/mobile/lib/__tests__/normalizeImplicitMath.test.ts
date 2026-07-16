import { fixImplicitExponents, normalizeImplicitMathInProse } from "@/lib/normalizeImplicitMath";

describe("normalizeImplicitMath", () => {
  it("wraps parenthesized algebra from model output", () => {
    const input = "Given equation: ( x^2 + 2 = 6 )\nStep 2: ( x = \\pm \\sqrt{4} )";
    const out = normalizeImplicitMathInProse(input);
    expect(out).toContain("$x^2 + 2 = 6$");
    expect(out).toContain("$x = \\pm \\sqrt{4}$");
  });

  it("BUG FIX regression: never re-wraps parentheticals INSIDE already-delimited $...$ inline math", () => {
    // Reported live on a quadratic-formula verification: the line
    //   $(-2 + \sqrt{3})^2 + 4(-2 + \sqrt{3}) + 1 = ... = 0$ ✓
    // was already wrapped in $...$, but MATH_IN_PARENS_RE re-wrapped each
    // (-2 + \sqrt{3}) in its own $...$, producing $$ and shattering the $
    // pairing across the whole message — \sqrt{3} then rendered as raw text
    // and adjacent "For x = ..." prose got glued into "Forx = ...". The
    // outer $...$ must be preserved verbatim.
    const line = "  $(-2 + \\sqrt{3})^2 + 4(-2 + \\sqrt{3}) + 1 = (4 - 4\\sqrt{3} + 3) + (-8 + 4\\sqrt{3}) + 1 = 0$ ✓";
    const out = normalizeImplicitMathInProse(line);
    expect(out).toBe(line);
    // No nested/extra $...$ injected inside the outer span, no $$.
    expect(out).not.toContain("$$");
    expect(out.match(/\$/g)?.length).toBe(2);
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

  it("BUG FIX regression: recognizes verification lines with any single-letter variable and 'Let' phrasing, not just x/y/z + 'For'", () => {
    // Reported live: "Let c = 3: 3^2 + 3^2 = 18" used variable "c" (not
    // x/y/z) and "Let" (not "For") — the old regex was hardcoded to
    // [xyz] + "For " only, so this line never got its math wrapped.
    const input = "Let c=3: 3^2+3^2=18 ✓";
    const out = normalizeImplicitMathInProse(input);
    expect(out).toContain("$3^2+3^2=18$");
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

  it("BUG FIX regression: wraps a bare LaTeX command embedded mid-sentence, not just whole-line equations", () => {
    // Reported live: "...or simplifying\\frac{8!}{6!}? 😄" rendered the raw
    // backslash command since it has no $...$ wrap at all and isn't a
    // whole-line equation for looksLikeBareEquation to key off — only the
    // command span itself (not the surrounding prose) must be wrapped.
    const input = "Want one with a twist? e.g., 0!, 10!, or simplifying\\frac{8!}{6!}? 😄";
    const out = normalizeImplicitMathInProse(input);
    expect(out).toBe(
      "Want one with a twist? e.g., 0!, 10!, or simplifying$\\frac{8!}{6!}$? 😄",
    );
  });

  it("does not double-wrap when the line already has dollar-delimited math", () => {
    const input = "We have $x = 2$ and also mention \\frac{1}{2} here.";
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

  it("BUG FIX regression: does not wrap LaTeX commands inside a \\[...\\] display-math span in $...$", () => {
    // Reported live (screenshots): "x = \\pm \\sqrt{4}" inside \\[...\\]
    // rendered in red. wrapInlineLatexCommands used to treat \\[ ... \\] as
    // plain prose and wrap each bare command (\\pm, \\sqrt{4}) in $...$
    // *before* markdownPreprocess.ts's BLOCK_MATH_BRACKET_RE converts the
    // \\[...\\] span into a ```math fence — leaving embedded, un-stripped $
    // characters in the fence body that KaTeX can't parse as bare LaTeX.
    const { normalizeImplicitMath } = require("@/lib/normalizeImplicitMath");
    const input = "Solve:\n\n\\[ x = \\pm \\sqrt{4} \\]\n\nDone.";
    const out = normalizeImplicitMath(input);
    expect(out).toContain("\\[ x = \\pm \\sqrt{4} \\]");
    expect(out).not.toContain("$\\pm$");
    expect(out).not.toContain("$\\sqrt{4}$");
  });

  it("BUG FIX regression: does not touch a $$...$$ display-math span either", () => {
    const { normalizeImplicitMath } = require("@/lib/normalizeImplicitMath");
    const input = "Solve:\n\n$$ x = \\pm \\sqrt{4} $$\n\nDone.";
    const out = normalizeImplicitMath(input);
    expect(out).toContain("$$ x = \\pm \\sqrt{4} $$");
  });

  it("BUG FIX regression: does not re-wrap parentheticals that already contain $...$", () => {
    // Live screenshot: "(excluded values: $x \\neq -3, 2$)" was wrapped as
    // `$excluded values: $x \\neq -3, 2$$`, inventing a trailing `$$` that
    // stole the next display-math opener — equations showed as raw LaTeX
    // and the Wait—prose paragraph was sucked into a MathBlock fence.
    const input =
      "- Domain restrictions (excluded values: $x \\neq -3, 2$)\n" +
      "- Cross-multiplication";
    expect(normalizeImplicitMathInProse(input)).toBe(input);
  });

  it("BUG FIX regression: does not wrap English parentheticals that mention math mid-sentence", () => {
    const input =
      "a hidden quadratic (e.g., in disguise like $x^4$) ✅";
    expect(normalizeImplicitMathInProse(input)).toBe(input);
  });

  it("still wraps a pure algebra parenthetical with an equals", () => {
    const input = "Solve: ( x^2 = 4 )";
    const out = normalizeImplicitMathInProse(input);
    expect(out).toContain("$x^2 = 4$");
  });
});

describe("fixImplicitExponents", () => {
  it("converts x2 to x^2", () => {
    expect(fixImplicitExponents("x2+2=6")).toBe("x^2+2=6");
  });
});
