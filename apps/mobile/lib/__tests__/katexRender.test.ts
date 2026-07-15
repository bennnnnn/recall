import { buildKatexStaticWebHtml, renderKatexHtml } from "@/lib/katexRender";

describe("renderKatexHtml", () => {
  it("renders algebra with katex markup and inlines fonts as data URIs (no CDN)", () => {
    const html = renderKatexHtml("x^2 + 2 = 6", { displayMode: true });
    expect(html).toContain('class="katex"');
    expect(html).toContain("x");
    // KaTeX fonts are vendored inline as base64 data URIs — no CDN fetch.
    expect(html).toContain("data:font/woff2;base64,");
    expect(html).not.toContain("cdn.jsdelivr.net");
    expect(html).not.toContain("url(fonts/");
  });

  it("renders sqrt and pm tokens", () => {
    const html = renderKatexHtml(String.raw`x = \pm \sqrt{4}`, { displayMode: false });
    expect(html).toContain('class="katex"');
  });
});

describe("buildKatexStaticWebHtml", () => {
  it("wraps pre-rendered katex for WebView", () => {
    const html = buildKatexStaticWebHtml("x^2 + 2 = 6", { displayMode: true });
    expect(html).toContain("<!DOCTYPE html>");
    expect(html).toContain('class="katex"');
    expect(html).toContain("ReactNativeWebView");
    // Single delayed height settle — not the old 40/250/800 triple (list shake).
    expect(html).toContain("setTimeout(postHeight, 300)");
    expect(html).not.toContain("setTimeout(postHeight, 250)");
    expect(html).not.toContain("setTimeout(postHeight, 800)");
  });
});
