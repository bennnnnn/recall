import { PREVIEW_CSP, MATH_PREVIEW_CSP } from "@/lib/previewSandbox";
import { buildMathWebHtml } from "@/lib/mathHtml";
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
});
