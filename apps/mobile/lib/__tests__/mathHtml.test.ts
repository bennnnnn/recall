import { PREVIEW_CSP, MATH_PREVIEW_CSP } from "@/lib/previewSandbox";
import { buildMathWebHtml, isHeavyMath, pickMathEngine } from "@/lib/mathHtml";
import { buildKatexStaticWebHtml } from "@/lib/katexRender";

describe("math WebView HTML", () => {
  it("injects the math CSP (allows MathJax CDN connect) into MathJax HTML", () => {
    const html = buildMathWebHtml("\\frac{1}{2}", {
      displayMode: true,
      engine: "mathjax",
      textColor: "#111",
      bgColor: "#fff",
    });
    expect(html).toContain(`content="${MATH_PREVIEW_CSP}"`);
    // MathJax's loader fetches tex extensions from the CDN at runtime, so the
    // math CSP must allow connect-src to it (the strict preview CSP blocks it
    // and the render falls back to the error div).
    expect(html).toContain("connect-src https://cdn.jsdelivr.net");
    expect(html).not.toContain("connect-src 'none'");
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

  it("adds an onerror handler and load-timeout fallback to the MathJax CDN script", () => {
    // BUG FIX: the CDN <script> tag had no onerror/timeout — offline, MathJax
    // never loads, ready() never fires, and the WebView rendered a silent
    // blank box with no indication anything went wrong.
    const html = buildMathWebHtml("\\frac{1}{2}", {
      displayMode: true,
      engine: "mathjax",
      textColor: "#111",
      bgColor: "#fff",
    });
    expect(html).toContain('onerror="showMathJaxFallback()"');
    expect(html).toContain("setTimeout(showMathJaxFallback, 8000)");
    expect(html).toContain("fallback-latex");
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

    it("still routes long or multi-line expressions to mathjax regardless of command", () => {
      expect(isHeavyMath("x".repeat(97))).toBe(true);
      expect(isHeavyMath("x = 1\ny = 2")).toBe(true);
    });
  });
});
