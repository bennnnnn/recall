import {
  looksLikeLatexFence,
  retagMathAndDiagramFences,
  stripRedundantDollarWrap,
} from "@/lib/mathFenceRetag";

describe("mathFenceRetag", () => {
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
