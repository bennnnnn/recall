import {
  MATH_TALL_LINE_HEIGHT,
  MATH_SCRIPT_LINE_HEIGHT,
  PROTECTED_ESCAPE_MARKER,
  latexHasStackedFrac,
  latexNeedsTallLine,
  mathRunLineHeight,
  parseSimpleLatex,
  segmentsToPlain,
  splitMathLines,
} from "@/lib/mathText";

describe("parseSimpleLatex", () => {
  it("parses superscripts", () => {
    const segs = parseSimpleLatex("x^2 + 2 = 6");
    expect(segmentsToPlain(segs)).toBe("x^2 + 2 = 6");
    expect(segs.some((s) => s.type === "sup" && s.value === "2")).toBe(true);
  });

  it("BUG FIX regression: unicode superscripts/subscripts parse as real scripts", () => {
    // OCR / models emit `x²` / `a₁₀` instead of caret form; without normalize
    // those glyphs stayed plain text and never became MathText sup/sub.
    const sup = parseSimpleLatex("x²");
    expect(sup.some((s) => s.type === "sup" && s.value === "2")).toBe(true);
    expect(segmentsToPlain(sup)).toBe("x^2");
    const sub = parseSimpleLatex("a₁₀");
    expect(sub.some((s) => s.type === "sub" && s.value === "10")).toBe(true);
    expect(segmentsToPlain(parseSimpleLatex(String.raw`n \in \mathbb{P}`))).toContain("ℙ");
  });

  it("handles pm and sqrt", () => {
    const segs = parseSimpleLatex(String.raw`x = \pm \sqrt{4}`);
    expect(segmentsToPlain(segs)).toContain("±");
    // Radicand sits under a combining overline ("4̅"), not in parens — no
    // parens needed since the bar itself delimits what's under the root.
    expect(segmentsToPlain(segs)).toContain("√4̅");
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

  it("BUG FIX regression: nth-root \\sqrt[n]{x} renders as √[n] with an overlined radicand, not raw", () => {
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\sqrt[3]{8}`))).toBe("√[3]8̅");
  });

  it("BUG FIX regression: \\sqrt{\\frac{...}{...}} renders the fraction, does not leak raw \\frac text", () => {
    // Reported live: "m = \pm\sqrt{\frac{M}{2}}" rendered the fraction as
    // literal, unrendered "\frac{M}{2}" text inside the root. Cause: the
    // \sqrt substitution used to be a flat `[^}]+` regex, which can't track
    // nested braces — it stopped at the FIRST "}" (the one closing \frac's
    // own "{M}"), corrupting the match instead of capturing the whole
    // radicand. \sqrt is now parsed like \frac (readGroup, brace-depth
    // aware), so a fraction inside a root parses and renders correctly.
    const segs = parseSimpleLatex(String.raw`m = \pm\sqrt{\frac{M}{2}}`);
    const plain = segmentsToPlain(segs);
    expect(plain).not.toContain("\\frac");
    expect(plain).not.toContain("{");
    expect(plain).not.toContain("}");
    expect(plain).toBe("m = ±√M̅/̅2̅");

    const sqrtSeg = segs.find((s) => s.type === "sqrt");
    expect(sqrtSeg).toBeTruthy();
    if (sqrtSeg?.type === "sqrt") {
      expect(sqrtSeg.body.some((s) => s.type === "frac")).toBe(true);
    }
  });

  it("BUG FIX regression: uppercase Greek + calculus/set symbols render as unicode, not raw backslash", () => {
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\Gamma + \Theta`))).toBe("Γ + Θ");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\Sigma \Omega \Pi`))).toBe("Σ Ω Π");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\partial f / \partial x`))).toContain("∂");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`x \in S`))).toContain("∈");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`A \subset B`))).toContain("⊂");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`a \equiv b`))).toContain("≡");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`(f \circ g)(2)`))).toBe("(f ∘ g)(2)");
    // `\cdot` used to eat `\cdots` → "·s" in factorial steps.
    expect(segmentsToPlain(parseSimpleLatex(String.raw`n \times (n-1) \times \cdots \times 1`))).toBe(
      "n × (n-1) × ⋯ × 1",
    );
    expect(segmentsToPlain(parseSimpleLatex(String.raw`1, 2, \ldots, n`))).toBe("1, 2, …, n");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`1, 2, \dots, n`))).toBe("1, 2, …, n");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`a \cdot b`))).toBe("a · b");
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

  it("degrades an unknown command by dropping a braced name, keeping the argument", () => {
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\varinjlim{x}`))).toBe("x");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\varinjlim{x}`))).not.toContain("\\");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\operatorname{lcm}(4,6)`))).toBe(
      "lcm(4,6)",
    );
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\overbrace{a+b}^{s}`))).toBe("a+b^s");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\underbrace{a+b}`))).toBe("a+b");
  });

  it("BUG FIX regression: \\left/\\right render as bare delimiters, not literal backslash text", () => {
    // `/\\left[\(\[\{|\\right[\)\]\}.]/` used to compile everything after the
    // first `[` into ONE character class, so `\right` never matched and a
    // dangling "\right)" leaked into the output.
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\left(\frac{1}{2}\right)`))).toBe("(1/2)");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\left[x\right]`))).toBe("[x]");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\left\{x\right\}`))).toBe("{x}");
  });

  it("BUG FIX regression: \\langle/\\rangle (and \\left\\langle) render as angle brackets", () => {
    // Live chat: vector components showed raw "\langle 2, 3, 4 \rangle"
    // because MathText had no mapping (KaTeX never sees inline $...$).
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\vec{d} = \langle 2, 3, 4 \rangle`))).toBe(
      "d⃗ = ⟨ 2, 3, 4 ⟩",
    );
    expect(
      segmentsToPlain(parseSimpleLatex(String.raw`\left\langle 2,-1,1 \right\rangle`)),
    ).toBe("⟨ 2,-1,1 ⟩");
  });

  it("BUG FIX regression: \\lor/\\land (and \\vee/\\wedge) render as logical glyphs", () => {
    // Inequality unions ask for `\lor` in the verified prompt; without these
    // MathText leaked raw "\lor" / "\land" on the native inline path.
    expect(segmentsToPlain(parseSimpleLatex(String.raw`x < -1 \lor x > 1`))).toBe(
      "x < -1 ∨ x > 1",
    );
    expect(segmentsToPlain(parseSimpleLatex(String.raw`x < -1 \vee x > 1`))).toBe(
      "x < -1 ∨ x > 1",
    );
    expect(segmentsToPlain(parseSimpleLatex(String.raw`P \land Q`))).toBe("P ∧ Q");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`P \wedge Q`))).toBe("P ∧ Q");
  });

  it("caps nested frac/sqrt depth instead of blowing the call stack", () => {
    let nested = "x";
    for (let i = 0; i < 40; i += 1) {
      nested = String.raw`\frac{${nested}}{1}`;
    }
    const segs = parseSimpleLatex(nested);
    expect(segs.length).toBeGreaterThan(0);
    // Deep overflow flattens to text rather than recursing forever.
    expect(JSON.stringify(segs).length).toBeLessThan(50_000);
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
    expect(
      segmentsToPlain(
        parseSimpleLatex(String.raw`\displaystyle\lim_{x \to 0} \frac{\sin x}{x}`),
      ),
    ).not.toContain("displaystyle");
    expect(
      segmentsToPlain(parseSimpleLatex(String.raw`a \quad \Rightarrow \quad b`)),
    ).toContain("⇒");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`a \Longrightarrow b`))).toBe("a ⟹ b");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`f: a \mapsto b`))).toBe("f: a ↦ b");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`x \le 2`))).toBe("x ≤ 2");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`x \ge 0`))).toBe("x ≥ 0");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`a \neq 0`))).toBe("a ≠ 0");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`a \ne 0`))).toBe("a ≠ 0");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`a \not= 0`))).toBe("a ≠ 0");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`a \neq 0`))).not.toContain("≡");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`a \ne 0`))).not.toBe("a ne 0");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`A \cup B \cap C`))).toBe("A ∪ B ∩ C");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`x \in \mathbb{R}`))).toContain("ℝ");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`n \in \mathbb{Z}`))).toContain("ℤ");
  });

  it("BUG FIX regression: \\boxed{...} unwraps to its inner content, not raw backslash text", () => {
    // \boxed has no plain-text equivalent (KaTeX/MathJax draw an actual
    // border) — the no-WebView (Expo Go) fallback used to show the literal
    // "\boxed{28}" instead of just "28".
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\boxed{28}`))).toBe("28");
  });

  it("BUG FIX regression: \\overline{...} draws a real combining overline, not raw backslash text", () => {
    // Reported live (screenshot): "0.\overline{714285}" (a repeating
    // decimal) rendered as the literal raw text "0.\overline{714285}" —
    // \overline had no entry in CMD_REPLACEMENTS or ROMAN_FUNCTIONS, so it
    // fell through to the generic \cmd fallback, which only consumes the
    // command NAME and leaves the following "{714285}" group as literal text.
    const plain = segmentsToPlain(parseSimpleLatex(String.raw`0.\overline{714285}`));
    expect(plain).not.toContain("\\overline");
    expect(plain).not.toContain("{");
    // Every digit carries a combining overline (U+0305), giving one
    // continuous line across the whole repeating block — not just the
    // last digit.
    expect(plain).toBe("0." + "714285".split("").map((c) => `${c}̅`).join(""));
  });

  it("accent commands (\\hat, \\vec, \\bar, \\dot, \\tilde, \\underline) render via combining marks", () => {
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\hat{x}`))).toBe("x̂");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\vec{v}`))).toBe("v⃗");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\bar{x}`))).toBe("x̄");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\dot{x}`))).toBe("ẋ");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\ddot{x}`))).toBe("ẍ");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\tilde{x}`))).toBe("x̃");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\underline{AB}`))).toBe(
      "A̲B̲",
    );
  });

  it("BUG FIX regression: decodes markdownPreprocess.ts's PROTECTED_ESCAPE_MARKER back to a literal backslash before any command table runs", () => {
    // markdownPreprocess.ts substitutes this marker in place of a backslash
    // immediately before punctuation-led commands inside $...$ math, to
    // survive markdown-it's own CommonMark backslash-escape rule. Simulate
    // that substituted text arriving here exactly as it does after a real
    // parse, and confirm \, \; \! resolve to their intended spacing once
    // decoded — not the marker itself, and not the bare punctuation the
    // escape rule would otherwise have left behind.
    const m = PROTECTED_ESCAPE_MARKER;
    expect(segmentsToPlain(parseSimpleLatex(`x^2${m},dx`))).toBe("x^2 dx");
    expect(segmentsToPlain(parseSimpleLatex(`a${m};b`))).toBe("a b");
    expect(segmentsToPlain(parseSimpleLatex(`5${m}!`))).toBe("5");
  });

  it("BUG FIX regression: \\binom{n}{k} renders as C(n,k), not raw backslash text", () => {
    // \binom has no stacked-column equivalent in plain text and had no
    // entry anywhere in this module — it fell through to the generic \cmd
    // fallback, leaving "\binom{5}{2}" visible verbatim in the no-WebView
    // (Expo Go) fallback.
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\binom{5}{2}`))).toBe("C(5,2)");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\dbinom{n}{k} = 1`))).toBe("C(n,k) = 1");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\tbinom{n}{k}`))).toBe("C(n,k)");
  });

  it("BUG FIX regression: \\begin{cases}/matrix environments render as readable text, not raw commands", () => {
    // MathBlock renders the WHOLE environment through this native parser
    // whenever the preview WebView is unavailable (Expo Go / no dev
    // build) — \begin{...}/\end{...} had no entry anywhere in this module,
    // so a piecewise function or matrix leaked its literal LaTeX source
    // ("\begin{cases}2x+y=5\\x-y=1\end{cases}") instead of rendering.
    expect(
      segmentsToPlain(parseSimpleLatex(String.raw`\begin{cases} 2x+y=5 \\ x-y=1 \end{cases}`)),
    ).toBe("2x+y=5; x-y=1");
    expect(
      segmentsToPlain(
        parseSimpleLatex(String.raw`\begin{cases} x^2 & x \geq 0 \\ -x^2 & x < 0 \end{cases}`),
      ),
    ).toBe("x^2 if x ≥ 0; -x^2 if x < 0");
    expect(
      segmentsToPlain(parseSimpleLatex(String.raw`\begin{pmatrix} 1 & 2 \\ 3 & 4 \end{pmatrix}`)),
    ).toBe("(1, 2; 3, 4)");
    expect(
      segmentsToPlain(parseSimpleLatex(String.raw`\begin{bmatrix} a & b \\ c & d \end{bmatrix}`)),
    ).toBe("[a, b; c, d]");
    expect(
      segmentsToPlain(
        parseSimpleLatex(String.raw`\begin{aligned} 2x + y &= 5 \\ x - y &= 1 \end{aligned}`),
      ),
    ).toBe("2x + y = 5;  x - y = 1");
    expect(
      segmentsToPlain(parseSimpleLatex(String.raw`\begin{multline}x = 1\end{multline}`)),
    ).toBe("x = 1");
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

describe("latexNeedsTallLine", () => {
  it("is true for stacked frac/sqrt so parent Text can clear the line above", () => {
    expect(latexNeedsTallLine(String.raw`\frac{x}{y}`)).toBe(true);
    expect(latexNeedsTallLine(String.raw`\dfrac{1}{2}`)).toBe(true);
    expect(latexNeedsTallLine(String.raw`\sqrt{25}`)).toBe(true);
    expect(MATH_TALL_LINE_HEIGHT).toBeGreaterThan(25);
    expect(mathRunLineHeight(String.raw`a^2(1+9+81)`)).toBe(MATH_SCRIPT_LINE_HEIGHT);
    expect(mathRunLineHeight(String.raw`\frac{1}{2}`)).toBe(MATH_TALL_LINE_HEIGHT);
    // Whole-paragraph astText (prose + several fracs) used to shrink to 34
    // and clip numerators. Stacked frac always needs the tall line box.
    expect(
      mathRunLineHeight(String.raw`\frac{1}{4}: \frac{8}{1/4}=32, 8 \cdot \frac{1}{4}=2`),
    ).toBe(MATH_TALL_LINE_HEIGHT);
    expect(
      mathRunLineHeight(
        "Now we split it for the ±: $x = \\frac{5+1}{2} = \\frac{6}{2} = 3$",
      ),
    ).toBe(MATH_TALL_LINE_HEIGHT);
  });

  it("is false for flat inline algebra", () => {
    expect(latexNeedsTallLine("x + 1 = 2")).toBe(false);
    expect(latexNeedsTallLine(String.raw`x^2`)).toBe(false);
  });
});

describe("latexHasStackedFrac", () => {
  it("is true only for frac commands (View-in-Text smudge)", () => {
    expect(latexHasStackedFrac(String.raw`\frac{d^2y}{dt^2}`)).toBe(true);
    expect(latexHasStackedFrac(String.raw`\dfrac{1}{2}`)).toBe(true);
    expect(latexHasStackedFrac(String.raw`\sqrt{25}`)).toBe(false);
    expect(latexHasStackedFrac("x + 1")).toBe(false);
  });
});

describe("BUG FIX regression: native inline parser leaks (raw LaTeX / bad format)", () => {
  // Each of these used to leak the raw command word or bare braces in
  // inline `$...$` math (native MathText, used for ALL inline math even
  // in dev builds). KaTeX display math had a readable fallback, but inline
  // did not — so the user saw "bigl(x+1bigr)", "a{=}", "red{x+1}", etc.
  it("strips sized delimiters (\\bigl/\\bigr/\\Bigl/\\biggl…) keeping the delimiter", () => {
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\bigl(x+1\bigr)`))).toBe("(x+1)");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\Bigl[x+1\Bigr]`))).toBe("[x+1]");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\biggl\{1\biggr\}`))).toBe("{1}");
  });

  it("maps big operators to glyphs (\\bigcup/\\oint/\\iint/…)", () => {
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\bigcup_{i=1}^{n} A_i`))).toContain("∪");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\oint_C F\,dr`))).toContain("∮");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\iint f`))).toContain("∬");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\iiint g`))).toContain("∭");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\oplus A`))).toBe("⊕ A");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\otimes B`))).toBe("⊗ B");
  });

  it("maps set-theory / relation glyphs (\\notin, \\degree, …)", () => {
    expect(segmentsToPlain(parseSimpleLatex(String.raw`x \notin A`))).toContain("∉");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`90\degree`))).toContain("°");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\bigcup_{i=1}^{n} A_i`))).toContain("∪");
  });

  it("unwraps \\overset/\\underset/\\stackrel to the base (no bare braces)", () => {
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\overset{a}{=}`))).toBe("=");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\stackrel{a}{=}`))).toBe("=");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\underset{x}{\cup}`))).toBe("∪");
  });

  it("unwraps \\color/\\textcolor to the base (no color name leaked)", () => {
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\color{red}{x+1}`))).toBe("x+1");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\textcolor{blue}{y}`))).toBe("y");
  });

  it("renders logic symbols (\\therefore/\\because) and mod (\\bmod/\\pmod)", () => {
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\therefore x`))).toBe("∴ x");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\because y`))).toBe("∵ y");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`a \bmod b`))).toContain("mod");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\pmod{7}`))).toBe("(mod 7)");
  });

  it("expands smallmatrix / Bmatrix / array environments (no env name leaked)", () => {
    expect(
      segmentsToPlain(parseSimpleLatex(String.raw`\begin{smallmatrix}1&2\\3&4\end{smallmatrix}`)),
    ).toBe("1, 2; 3, 4");
    expect(
      segmentsToPlain(parseSimpleLatex(String.raw`\begin{Bmatrix}1&2\\3&4\end{Bmatrix}`)),
    ).toBe("{1, 2; 3, 4}");
    // array strips its column spec ({cc}) — it must not leak as "{cc}".
    expect(
      segmentsToPlain(parseSimpleLatex(String.raw`\begin{array}{cc}1&2\\3&4\end{array}`)),
    ).toBe("1 2;  3 4");
  });

  it("splits \\substack rows (no stray backslash from the row separator)", () => {
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\substack{a\\b}`))).toBe("a; b");
  });

  it("does not let \\pm eat the \\pmod prefix", () => {
    // \pm → ± must not match inside \pmod (regression guard for the \pm
    // word-boundary fix that lets \pmod reach its own rule).
    expect(segmentsToPlain(parseSimpleLatex(String.raw`x \pm y`))).toBe("x ± y");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\pmod{7}`))).toBe("(mod 7)");
  });
});
