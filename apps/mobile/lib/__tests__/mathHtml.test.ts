import { PREVIEW_CSP, MATH_PREVIEW_CSP } from "@/lib/previewSandbox";
import { buildMathWebHtml, isHeavyMath, pickMathEngine } from "@/lib/mathHtml";
import { buildMathjaxWebHtml } from "@/lib/mathHtmlMathjax";
import { buildKatexStaticWebHtml } from "@/lib/katexRender";

describe("math WebView HTML", () => {
  it("injects the math CSP (no network egress — MathJax is vendored inline) into MathJax HTML", () => {
    const html = buildMathjaxWebHtml("\\frac{1}{2}", {
      displayMode: true,
      engine: "mathjax",
      textColor: "#111",
      bgColor: "#fff",
    });
    expect(html).toContain(`content="${MATH_PREVIEW_CSP}"`);
    // MathJax (tex-svg) is vendored and inlined; its tex extensions are
    // pre-bundled and SVG output needs no font fetches, so the math CSP keeps
    // connect-src 'none' — the same hard egress block as the preview CSP.
    expect(html).toContain("connect-src 'none'");
    // No external <script src> pulls MathJax from a CDN anymore (the bundle is
    // inlined). The bundle does contain dormant speech-rule-engine CDN URLs
    // as strings, but those never execute under our config and connect-src
    // 'none' blocks them regardless — so we assert on script srcs, not the
    // bare host string.
    expect(html).not.toContain('src="https://cdn.jsdelivr.net');
    expect(html).not.toContain('src="https://cdnjs.cloudflare.com');
  });

  it("injects the strict preview CSP into KaTeX static HTML", () => {
    const html = buildKatexStaticWebHtml("x^2", {
      displayMode: false,
      textColor: "#111",
      bgColor: "#fff",
    });
    expect(html).toContain(`content="${PREVIEW_CSP}"`);
    expect(html).toContain("connect-src 'none'");
  });

  it("buildMathWebHtml stays on the KaTeX path (MathJax is a separate async chunk)", () => {
    const html = buildMathWebHtml("\\frac{1}{2}", {
      displayMode: true,
      textColor: "#111",
      bgColor: "#fff",
    });
    expect(html).not.toContain("__webpack_modules__");
    expect(html).not.toContain("tex2svgPromise");
    expect(() =>
      buildMathWebHtml("\\frac{1}{2}", {
        displayMode: true,
        engine: "mathjax",
        textColor: "#111",
        bgColor: "#fff",
      }),
    ).toThrow(/mathHtmlMathjax/);
  });

  it("inlines the vendored MathJax bundle (no external script src) and keeps the load-timeout fallback", () => {
    // The MathJax bundle is inlined as a <script>...</script> block (no
    // external src) so it renders fully offline. The 8s load-timeout remains
    // as a safety net against a pathological init hang; the fallback div still
    // shows raw LaTeX if MathJax fails to produce output.
    const html = buildMathjaxWebHtml("\\frac{1}{2}", {
      displayMode: true,
      engine: "mathjax",
      textColor: "#111",
      bgColor: "#fff",
    });
    expect(html).not.toContain('src="https://cdn.jsdelivr.net');
    expect(html).not.toContain('onerror="showMathJaxFallback()"');
    expect(html).toContain("setTimeout(showMathJaxFallback, 8000)");
    expect(html).toContain("fallback-latex");
    // The inlined tex-svg bundle defines the webpack module system; spot-check
    // a known marker so a regression to an empty/CDN bundle is caught.
    expect(html).toContain("__webpack_modules__");
    expect(html).toContain("tex2svgPromise");
  });

  describe("isHeavyMath / pickMathEngine", () => {
    it("BUG FIX regression: routes KaTeX-supported commands to katex, not mathjax", () => {
      // Empirically verified against the bundled KaTeX 0.17.0: these all
      // render correctly under katex.renderToString with throwOnError:true,
      // so routing them to MathJax was unnecessary CDN exposure (the single
      // biggest offline-rendering failure mode).
      const supported = [
        "\\frac{1}{2}",
        "\\int_0^1 x\\,dx",
        "\\sum_{i=1}^n i",
        "\\prod_{i=1}^n i",
        "\\binom{n}{k}",
        "\\begin{pmatrix} 1 & 2 \\\\ 3 & 4 \\end{pmatrix}",
        "\\begin{aligned} a &= b \\end{aligned}",
        "\\begin{cases} 1 & x > 0 \\\\ 0 & x \\le 0 \\end{cases}",
      ];
      for (const expr of supported) {
        expect(isHeavyMath(expr)).toBe(false);
        expect(pickMathEngine(expr)).toBe("katex");
      }
    });

    it("still routes the environments KaTeX genuinely doesn't support to mathjax", () => {
      expect(isHeavyMath("\\begin{multline} a \\end{multline}")).toBe(true);
      expect(isHeavyMath("\\begin{eqnarray} a &=& b \\end{eqnarray}")).toBe(true);
      expect(pickMathEngine("\\begin{multline} a \\end{multline}")).toBe("mathjax");
    });

    it("BUG FIX regression: does not route long or multi-line KaTeX-supported expressions to mathjax", () => {
      // Reported live: a multi-step derivation (long AND multi-line — the
      // exact shape of a \begin{aligned} block) rendered as a permanently
      // blank box. The old length/newline heuristic routed it to MathJax's
      // CDN despite the verification above confirming local KaTeX renders
      // it fine — unreachable CDN meant it never rendered at all.
      expect(isHeavyMath("x".repeat(97))).toBe(false);
      expect(isHeavyMath("x = 1\ny = 2")).toBe(false);
      const multiStepAligned =
        "\\begin{aligned}\nc^2 + c^2 &= 2c^2 \\\\\n3^2 + 3^2 &= 9 + 9 = 18\n\\end{aligned}";
      expect(isHeavyMath(multiStepAligned)).toBe(false);
      expect(pickMathEngine(multiStepAligned)).toBe("katex");
    });
  });
});
