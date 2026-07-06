import { PREVIEW_CSP } from "@/lib/previewSandbox";
import { buildMathWebHtml } from "@/lib/mathHtml";
import { buildKatexStaticWebHtml } from "@/lib/katexRender";

describe("math WebView HTML", () => {
  it("injects preview CSP into MathJax HTML", () => {
    const html = buildMathWebHtml("\\frac{1}{2}", {
      displayMode: true,
      engine: "mathjax",
      textColor: "#111",
      bgColor: "#fff",
    });
    expect(html).toContain(`content="${PREVIEW_CSP}"`);
    expect(html).toContain("connect-src 'none'");
  });

  it("injects preview CSP into KaTeX static HTML", () => {
    const html = buildKatexStaticWebHtml("x^2", {
      displayMode: false,
      textColor: "#111",
      bgColor: "#fff",
    });
    expect(html).toContain(`content="${PREVIEW_CSP}"`);
    expect(html).toContain("connect-src 'none'");
  });
});
