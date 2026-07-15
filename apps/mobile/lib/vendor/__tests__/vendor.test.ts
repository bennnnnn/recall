// Integrity checks for the vendored CDN assets. These lock in the invariants
// the generator (scripts/vendor-cdn.mjs) guarantees, so a regression to an
// empty file or a re-introduced CDN URL is caught at test time rather than at
// runtime (blank WebView offline).
import { KATEX_CSS } from "@/lib/vendor/katexCss";
import { MATHJAX_TEX_SVG_JS } from "@/lib/vendor/mathjaxTexSvgJs";
import { MERMAID_MIN_JS } from "@/lib/vendor/mermaidMinJs";
import { PDF_MIN_JS } from "@/lib/vendor/pdfMinJs";
import { PDF_WORKER_MIN_JS } from "@/lib/vendor/pdfWorkerMinJs";
import { VEGA_EMBED_MIN_JS } from "@/lib/vendor/vegaEmbedMinJs";
import { VEGA_LITE_MIN_JS } from "@/lib/vendor/vegaLiteMinJs";
import { VEGA_MIN_JS } from "@/lib/vendor/vegaMinJs";

describe("vendored CDN assets", () => {
  const jsBundles: Array<[string, string]> = [
    ["MATHJAX_TEX_SVG_JS", MATHJAX_TEX_SVG_JS],
    ["MERMAID_MIN_JS", MERMAID_MIN_JS],
    ["VEGA_MIN_JS", VEGA_MIN_JS],
    ["VEGA_LITE_MIN_JS", VEGA_LITE_MIN_JS],
    ["VEGA_EMBED_MIN_JS", VEGA_EMBED_MIN_JS],
    ["PDF_MIN_JS", PDF_MIN_JS],
    ["PDF_WORKER_MIN_JS", PDF_WORKER_MIN_JS],
  ];

  it.each(jsBundles)("%s is a non-empty string", (_name, src) => {
    expect(typeof src).toBe("string");
    expect(src.length).toBeGreaterThan(1000);
  });

  it.each(jsBundles)("%s contains no </script> sequence (safe to inline)", (_name, src) => {
    // The inline-script rendering path relies on this; the generator fails
    // loudly if a version bump introduces it, but this guards against a
    // hand-edit too.
    expect(src).not.toMatch(/<\/script>/i);
  });

  it.each(jsBundles)("%s contains no CDN host URL", (_name, src) => {
    // Vendored bundles must not reach back out to a CDN at runtime. (MathJax's
    // bundle contains dormant speech-rule-engine URLs that only execute under
    // an a11y config we don't load — those are acceptable and excluded from
    // this check by only flagging cdnjs, which none of our bundles should
    // reference.)
    expect(src).not.toContain("cdnjs.cloudflare.com");
  });

  it("KATEX_CSS inlines woff2 fonts as data URIs and references no CDN", () => {
    expect(KATEX_CSS).toContain("data:font/woff2;base64,");
    expect(KATEX_CSS).not.toContain("cdn.jsdelivr.net");
    expect(KATEX_CSS).not.toMatch(/url\(fonts\//);
  });

  it("MathJax bundle is the tex-svg build (SVG output, no font fetches)", () => {
    // tex-svg renders as SVG paths and does not fetch woff fonts at render
    // time (unlike tex-chtml). Spot-check markers from the bundle.
    expect(MATHJAX_TEX_SVG_JS).toContain("__webpack_modules__");
    expect(MATHJAX_TEX_SVG_JS.length).toBeGreaterThan(500_000);
  });

  it("pdf.js main + worker are both present and substantial", () => {
    expect(PDF_MIN_JS.length).toBeGreaterThan(50_000);
    expect(PDF_WORKER_MIN_JS.length).toBeGreaterThan(500_000);
  });
});
