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

  it("display math keeps vertical margin and a transparent canvas (no gray card)", () => {
    const html = renderKatexHtml(String.raw`\frac{x}{y}`, {
      displayMode: true,
      bgColor: "transparent",
    });
    expect(html).toContain(".katex-display{margin:0.6em 0;}");
    expect(html).toContain("background:transparent");
  });

  it("compact / inline math does not add display-block vertical margin", () => {
    const compact = renderKatexHtml("x^2", { displayMode: true, compact: true });
    expect(compact).toContain(".katex-display{margin:0;}");
    const inline = renderKatexHtml("x^2", { displayMode: false });
    expect(inline).toContain(".katex-display{margin:0;}");
  });

  it("falls back for oversized latex instead of hanging", () => {
    const huge = "x".repeat(5000);
    const html = renderKatexHtml(huge, { displayMode: true });
    expect(html).toContain("<code>");
    expect(html).not.toContain('class="katex"');
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

  it("BUG FIX regression: long display math can scroll horizontally instead of clipping", () => {
    // Live chat: wide equations were cut off at the bubble edge because
    // body/math-root used overflow:hidden and the WebView had scroll off.
    const html = buildKatexStaticWebHtml(
      String.raw`\vec{d}\cdot\vec{n}=(2)(2)+(3)(-1)+(4)(1)=5`,
      { displayMode: true },
    );
    expect(html).toContain("overflow-x: auto");
    expect(html).toContain("width:max-content");
    expect(html).not.toMatch(/html, body \{[^}]*overflow: hidden/);
  });
});
