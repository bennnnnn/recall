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
    expect(segs).toEqual([
      { type: "frac", num: [{ type: "text", value: "a" }], den: [{ type: "text", value: "b" }] },
    ]);
  });

  it("BUG FIX regression: \\frac numerator/denominator render as nested segments (superscripts inside a fraction)", () => {
    // \frac{x^2}{4} used to flatten the numerator to the literal string "x^2"
    // (caret shown), not the superscript x². num/den are now MathSegment[] so
    // superscripts/subscripts render correctly inside a fraction.
    const segs = parseSimpleLatex(String.raw`\frac{x^2}{4}`);
    const frac = segs.find((s) => s.type === "frac");
    expect(frac).toBeTruthy();
    if (frac?.type === "frac") {
      expect(frac.num.some((s) => s.type === "sup" && s.value === "2")).toBe(true);
      expect(segmentsToPlain(frac.num)).toBe("x^2");
      expect(segmentsToPlain(frac.den)).toBe("4");
    }
  });

  it("BUG FIX regression: normalizes \\dfrac/\\tfrac/\\cfrac to \\frac (no raw \\dfrac inline)", () => {
    expect(parseSimpleLatex(String.raw`\dfrac{a}{b}`)).toEqual([
      { type: "frac", num: [{ type: "text", value: "a" }], den: [{ type: "text", value: "b" }] },
    ]);
    expect(parseSimpleLatex(String.raw`\tfrac{1}{2}`).some((s) => s.type === "frac")).toBe(true);
    expect(parseSimpleLatex(String.raw`\cfrac{a}{b}`).some((s) => s.type === "frac")).toBe(true);
  });

  it("BUG FIX regression: nth-root \\sqrt[n]{x} renders as √[n](x), not raw", () => {
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\sqrt[3]{8}`))).toBe("√[3](8)");
  });

  it("BUG FIX regression: uppercase Greek + calculus/set symbols render as unicode, not raw backslash", () => {
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\Gamma + \Theta`))).toBe("Γ + Θ");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\Sigma \Omega \Pi`))).toBe("Σ Ω Π");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\partial f / \partial x`))).toContain("∂");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`x \in S`))).toContain("∈");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`A \subset B`))).toContain("⊂");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`a \equiv b`))).toContain("≡");
  });

  it("BUG FIX regression: accents render via Unicode combining marks, not raw \\hat/\\vec", () => {
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\hat{x}`))).toBe("x\u0302");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\vec{v}`))).toBe("v\u20D7");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\bar{x}`))).toBe("x\u0304");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\dot{y}`))).toBe("y\u0307");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\overline{AB}`))).toContain("\u0304");
  });

  it("BUG FIX regression: \\mathbb{R/Z/N/...} renders as double-struck unicode, not raw", () => {
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\mathbb{R}`))).toBe("ℝ");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`x \in \mathbb{Z}`))).toContain("ℤ");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\mathbb{C}`))).toBe("ℂ");
    // Unknown double-struck letter falls back to itself (no raw \mathbb).
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\mathbb{A}`))).toBe("A");
  });

  it("BUG FIX regression: \\binom{n}{k} renders as choose notation, not raw", () => {
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\binom{n}{k}`))).toBe("C(n, k)");
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

  it("BUG FIX regression: does not split a multi-line \\begin{…} environment", () => {
    // aligned/cases/matrix use newlines between rows and must render as ONE
    // block — splitting shattered them into per-row KaTeX parse errors.
    const aligned = String.raw`\begin{aligned} x^2 &= 4 \\ x &= \pm 2 \end{aligned}`;
    expect(splitMathLines(aligned)).toEqual([aligned]);
    const cases = String.raw`\begin{cases} x & 1 \\ y & 2 \end{cases}`;
    expect(splitMathLines(cases)).toEqual([cases]);
    // Independent equations (no environment) still split.
    expect(splitMathLines("x = 1\ny = 2")).toEqual(["x = 1", "y = 2"]);
  });
});
