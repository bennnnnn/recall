import { parseSimpleLatex, segmentsToPlain, splitMathLines } from "@/lib/mathText";

describe("parseSimpleLatex", () => {
  it("parses superscripts", () => {
    const segs = parseSimpleLatex("x^2 + 2 = 6");
    expect(segmentsToPlain(segs)).toBe("x^2 + 2 = 6");
    expect(segs.some((s) => s.type === "sup" && s.value === "2")).toBe(true);
  });

  it("handles pm and sqrt", () => {
    const segs = parseSimpleLatex(String.raw`x = \pm \sqrt{4}`);
    expect(segmentsToPlain(segs)).toContain("±");
    expect(segmentsToPlain(segs)).toContain("√(4)");
  });

  it("parses fractions", () => {
    const segs = parseSimpleLatex(String.raw`\frac{a}{b}`);
    expect(segs).toEqual([{ type: "frac", num: "a", den: "b" }]);
  });

  it("BUG FIX regression: renders known function names without the leading backslash", () => {
    // \log_2(2) used to render literally as "\log_2(2)" in the no-WebView
    // (Expo Go) plain-text fallback since \log wasn't in CMD_REPLACEMENTS.
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\log_2(2)`))).toBe("log_2(2)");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\sin(x) + \cos(x)`))).toBe(
      "sin(x) + cos(x)",
    );
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\lim_{x \to 0}`))).toBe("lim_x → 0");
  });

  it("still shows the backslash for a genuinely unknown command", () => {
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\widehat{x}`))).toContain("\\widehat");
  });

  it("BUG FIX regression: \\left/\\right render as bare delimiters, not literal backslash text", () => {
    // `/\\left[\(\[\{|\\right[\)\]\}.]/` used to compile everything after the
    // first `[` into ONE character class, so `\right` never matched and a
    // dangling "\right)" leaked into the output.
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\left(\frac{1}{2}\right)`))).toBe("(1/2)");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\left[x\right]`))).toBe("[x]");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\left\{x\right\}`))).toBe("{x}");
  });

  it("BUG FIX regression: \\sum/\\prod/\\int render as unicode glyphs, not the literal words", () => {
    // These were misfiled into ROMAN_FUNCTIONS and rendered as "sum(...)"/
    // "prod(...)"/"int(...)" instead of the actual big-operator symbols.
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\sum_{i=1}^{n} i`))).toBe("Σ_i=1^n i");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\prod_{i=1}^{n} i`))).toContain("∏");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\int_0^1 x\,dx`))).toContain("∫");
  });

  it("BUG FIX regression: previously-missing Greek letters and arrows render as unicode, not raw backslash text", () => {
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\delta \sigma \omega`))).toBe("δ σ ω");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`a \implies b`))).toBe("a ⇒ b");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`a \Longrightarrow b`))).toBe("a ⟹ b");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`f: a \mapsto b`))).toBe("f: a ↦ b");
  });

  it("BUG FIX regression: \\boxed{...} unwraps to its inner content, not raw backslash text", () => {
    // \boxed has no plain-text equivalent (KaTeX/MathJax draw an actual
    // border) — the no-WebView (Expo Go) fallback used to show the literal
    // "\boxed{28}" instead of just "28".
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\boxed{28}`))).toBe("28");
  });
});

describe("splitMathLines", () => {
  it("splits a multi-equation fence body into separate lines", () => {
    expect(splitMathLines("x^2 = 5 - 1\nx^2 = 4")).toEqual(["x^2 = 5 - 1", "x^2 = 4"]);
  });

  it("returns a single-element array for a one-line body", () => {
    expect(splitMathLines("x^2 = 4")).toEqual(["x^2 = 4"]);
  });

  it("drops blank lines", () => {
    expect(splitMathLines("x = 2\n\nx = -2\n")).toEqual(["x = 2", "x = -2"]);
  });
});
