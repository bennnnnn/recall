import { buildKatexStaticWebHtml, renderKatexHtml } from "@/lib/katexRender";

describe("renderKatexHtml", () => {
  it("renders algebra with katex markup", () => {
    const html = renderKatexHtml("x^2 + 2 = 6", { displayMode: true });
    expect(html).toContain('class="katex"');
    expect(html).toContain("x");
    expect(html).toContain("cdn.jsdelivr.net/npm/katex");
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
  });
});
