import {
  isHeavyInlineMath,
  looksLikeLatexFence,
  retagMathAndDiagramFences,
  stripEmbeddedDollarWraps,
  stripRedundantDollarWrap,
} from "@/lib/mathFenceRetag";

describe("mathFenceRetag", () => {
  it("isHeavyInlineMath: only \\begin{…} environments are heavy", () => {
    // Environments the native MathText path can't lay out → route to WebView.
    expect(isHeavyInlineMath(String.raw`\begin{matrix}a&b\\c&d\end{matrix}`)).toBe(true);
    expect(isHeavyInlineMath(String.raw`\begin{cases} x & 1 \\ y & 2 \end{cases}`)).toBe(true);
    expect(isHeavyInlineMath(String.raw`\begin{aligned} x &= 1 \\ y &= 2 \end{aligned}`)).toBe(true);
    expect(isHeavyInlineMath(String.raw`\begin{pmatrix}1\\2\end{pmatrix}`)).toBe(true);
    // Common inline math (no \begin) stays native — NOT heavy.
    expect(isHeavyInlineMath(String.raw`x^2 + 1`)).toBe(false);
    expect(isHeavyInlineMath(String.raw`\frac{a}{b}`)).toBe(false);
    expect(isHeavyInlineMath(String.raw`\sqrt{4}`)).toBe(false);
    expect(isHeavyInlineMath(String.raw`\mathbb{R}`)).toBe(false);
    expect(isHeavyInlineMath(String.raw`\hat{x}`)).toBe(false);
  });

  it("retags latex fence to math", () => {
    const input = "```latex\n\\text{Area} = 8 \\times 5\n```";
    const out = retagMathAndDiagramFences(input);
    expect(out).toContain("```math");
  });

  it("does not retag json geometry to geometry fence", () => {
    const input = '```json\n{"type":"square","side":5,"unit":"cm"}\n```';
    const out = retagMathAndDiagramFences(input);
    expect(out).toContain("```json");
    expect(out).not.toContain("```geometry");
  });

  it("detects latex body", () => {
    expect(looksLikeLatexFence("\\text{Area} = L \\times W")).toBe(true);
    expect(looksLikeLatexFence(String.raw`x = \pm \sqrt{4}`)).toBe(true);
  });

  it("detects factorial definitions as math, not code", () => {
    expect(looksLikeLatexFence("0! = 1")).toBe(true);
    expect(looksLikeLatexFence("5! = 5 \\times 4 \\times 3 \\times 2 \\times 1")).toBe(true);
  });

  it("BUG FIX regression: \\boxed{...} is detected as latex, not a plain code fence", () => {
    // \boxed wasn't in LATEX_CMD_RE, so a fence body that's just
    // "\boxed{28}" (a common LLM final-answer convention, with no "="
    // sign for looksLikeAlgebraLine to key off) fell through to a plain
    // code block instead of rendering as math.
    expect(looksLikeLatexFence(String.raw`\boxed{28}`)).toBe(true);
  });

  it("retags plain fences with algebra or latex to math", () => {
    const input = [
      "Step 1:",
      "```",
      "x^2 + 2 - 2 = 6 - 2",
      "```",
      "```",
      String.raw`x = \pm \sqrt{4}`,
      "```",
    ].join("\n");
    const out = retagMathAndDiagramFences(input);
    expect(out).toContain("```math");
    expect(out).not.toMatch(/```\n\s*x\^2/);
  });

  it("BUG FIX regression: detects log/trig/sum-style LaTeX commands with subscripts", () => {
    // \b treats `_` as a word char, so a naive trailing \b after the command
    // name never matches before a subscript — \log_2, \lim_{x\to0}, etc.
    expect(looksLikeLatexFence(String.raw`x = \log_2(2)`)).toBe(true);
    expect(looksLikeLatexFence(String.raw`\log_2(2) = 1`)).toBe(true);
    expect(looksLikeLatexFence(String.raw`\lim_{x \to 0} \sin(x)`)).toBe(true);
    expect(looksLikeLatexFence(String.raw`\sum_{i=1}^{n} i`)).toBe(true);
  });

  it("BUG FIX regression: detects brace-grouped exponents/subscripts without a backslash command", () => {
    // Braces alone used to disqualify a line as "looks like code" — but
    // `2^{1}` / `a_{n}` are ordinary LaTeX grouping, not code syntax.
    expect(looksLikeLatexFence("2^{1} + 5 = 2 + 5 = 7")).toBe(true);
  });

  it("BUG FIX regression: detects a multi-step \\begin{aligned} derivation despite having more than 4 lines", () => {
    // The line-count safety cap ran before the LATEX_CMD_RE check, so any
    // \begin{aligned}...\end{aligned} block with more than 4 lines (routine
    // for a 3+ step derivation) was rejected as "not math" before the
    // \times/\text{/\begin match ever ran, and fell back to a plain
    // syntax-highlighted code block instead of rendering as typeset math.
    const body = [
      String.raw`\begin{aligned}`,
      String.raw`A &= \pi \times 4^{2} \\`,
      String.raw`  &= \pi \times 16 \\`,
      String.raw`  &= 16\pi \\`,
      String.raw`  &\approx 50.27\ \text{cm}^{2}`,
      String.raw`\end{aligned}`,
    ].join("\n");
    expect(looksLikeLatexFence(body)).toBe(true);
  });

  it("BUG FIX regression: detects \\pi as a LaTeX command", () => {
    // \pi was missing from LATEX_CMD_RE entirely — one of the most common
    // LaTeX commands — so a formula like the circle area general form
    // fell through to a plain code block instead of typeset math.
    expect(looksLikeLatexFence(String.raw`A \;=\; \pi \, r^{2}`)).toBe(true);
    expect(looksLikeLatexFence(String.raw`C = 2\pi r`)).toBe(true);
  });

  it("BUG FIX regression: detects arrow/implication commands (\\Longrightarrow, \\to, etc.)", () => {
    // Arrow commands showing "this step leads to that step" are routine in
    // multi-step derivations but were entirely missing from LATEX_CMD_RE.
    // Without a match here the body fell through to the bare-algebra
    // fallback, which then rejected it anyway because \; (thin space)
    // contains a literal ";" — one of that fallback's own code-disqualifier
    // characters. Falls back to a plain code block instead of typeset math.
    expect(
      looksLikeLatexFence(String.raw`2^x + 5 = 7 \;\Longrightarrow\; 2^x = 7 - 5`),
    ).toBe(true);
    expect(looksLikeLatexFence(String.raw`x \to 0`)).toBe(true);
    expect(looksLikeLatexFence(String.raw`p \implies q`)).toBe(true);
  });

  it("BUG FIX regression: classifies a fence body that's ENTIRELY wrapped in $...$ with no other LaTeX command", () => {
    // "$2^x = 2$" has no recognized LATEX_CMD_RE keyword of its own, and
    // the bare-algebra fallback's character class excludes "$" — so without
    // unwrapping first, this fell through to a plain code block even though
    // it's unambiguously a redundant inline-math wrap around real algebra.
    expect(looksLikeLatexFence(String.raw`$2^x = 2$`)).toBe(true);
  });

  describe("stripRedundantDollarWrap", () => {
    it("BUG FIX regression: strips a redundant $...$ wrap from a math fence body", () => {
      // A ```math fence body should be bare LaTeX. When the model wraps it
      // in $...$ anyway, KaTeX (which doesn't understand $ as syntax) fails
      // to parse and renders the raw source in errorColor (red) instead of
      // typeset math — this is what fixes "$= \pi \times 16$" showing up
      // as literal red text.
      expect(stripRedundantDollarWrap(String.raw`$= \pi \times 16$`)).toBe(
        String.raw`= \pi \times 16`,
      );
    });

    it("strips a redundant $$...$$ wrap", () => {
      expect(stripRedundantDollarWrap(String.raw`$$x^2 = 4$$`)).toBe(String.raw`x^2 = 4`);
    });

    it("leaves bare LaTeX (no wrap) untouched", () => {
      expect(stripRedundantDollarWrap(String.raw`\pi \times 16`)).toBe(String.raw`\pi \times 16`);
    });

    it("leaves a lone leading or trailing $ untouched (not a matched wrap)", () => {
      expect(stripRedundantDollarWrap("$5 + x")).toBe("$5 + x");
    });
  });

  describe("stripEmbeddedDollarWraps", () => {
    it("BUG FIX regression: unwraps scattered $...$ wraps around individual commands, not just a whole-body wrap", () => {
      // Reported live (screenshot): "n! = n $\times$ (n-1)!" rendered in red
      // inside a math fence. The model wrapped only the \times command in
      // $...$, leaving the rest of the line bare — stripRedundantDollarWrap
      // only catches a wrap around the ENTIRE body, not this scattered case.
      expect(stripEmbeddedDollarWraps(String.raw`n! = n $\times$ (n-1)!`)).toBe(
        String.raw`n! = n \times (n-1)!`,
      );
    });

    it("unwraps multiple scattered wraps on the same line", () => {
      expect(
        stripEmbeddedDollarWraps(
          String.raw`(1-1)! = 0! = $\frac{1!}{1}$ = $\frac{1}{1}$ = 1`,
        ),
      ).toBe(String.raw`(1-1)! = 0! = \frac{1!}{1} = \frac{1}{1} = 1`);
    });

    it("unwraps a scattered $$...$$ wrap too", () => {
      expect(stripEmbeddedDollarWraps(String.raw`a = $$\pi r^2$$ for a circle`)).toBe(
        String.raw`a = \pi r^2 for a circle`,
      );
    });

    it("leaves bare LaTeX with no $ untouched", () => {
      expect(stripEmbeddedDollarWraps(String.raw`\pi \times 16`)).toBe(String.raw`\pi \times 16`);
    });

    it("leaves an unmatched lone $ untouched", () => {
      expect(stripEmbeddedDollarWraps("$5 + x")).toBe("$5 + x");
    });
  });

  it("does not swallow prose between two already-tagged math fences", () => {
    // A closing ``` for the first ```math fence must never be mistaken for
    // the opener of a new bare fence that then swallows everything up to
    // the second ```math fence's own opener.
    const input = [
      "Simplifies to:",
      "```math",
      "x^2 = 4",
      "```",
      "",
      "2. Take the square root of both sides:",
      String.raw`x = \pm\sqrt{4}`,
      "",
      "Simplifies to:",
      "```math",
      String.raw`x = \pm2`,
      "```",
    ].join("\n");

    const out = retagMathAndDiagramFences(input);

    expect(out).toContain("```math\nx^2 = 4\n```");
    expect(out).toContain("```math\n" + String.raw`x = \pm2` + "\n```");
    expect(out).toContain("2. Take the square root of both sides:");
    // The step label/prose must never end up re-tagged as its own math fence.
    expect(out).not.toContain("```math\n2. Take the square root");
  });
});
