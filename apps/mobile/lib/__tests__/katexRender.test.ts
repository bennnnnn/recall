import { buildKatexStaticWebHtml, renderKatexHtml } from "@/lib/katexRender";
import { PROTECTED_ESCAPE_MARKER, PROTECTED_MATH_STAR_MARKER, PROTECTED_MATH_UNDERSCORE_MARKER } from "@/lib/mathText";

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

  it.each([
    String.raw`9^{\frac{1}{6}}`,
    String.raw`\int_0^1 x^2\,dx=\frac{1}{3}`,
    String.raw`\begin{pmatrix}1&2\\3&4\end{pmatrix}`,
  ])("keeps complex math %s readable with room for script ink", (latex) => {
    const html = renderKatexHtml(latex, { displayMode: true, compact: true });
    expect(html).toContain('class="katex"');
    expect(html).not.toContain('class="math-fallback"');
    expect(html).toContain("font-size:20px");
    expect(html).toContain(".katex{color:inherit;font-size:1em;}");
    expect(html).toContain(".math-root{padding:4px 2px;");
  });

  it.each([
    String.raw`\int_0^1 x^2\,dx=\frac{1}{3}`,
    String.raw`\sum_{n=1}^{\infty}\frac{1}{n^2}=\frac{\pi^2}{6}`,
    String.raw`\begin{pmatrix}1&2\\3&4\end{pmatrix}`,
    String.raw`x*y`,
  ])("restores protected markdown source before typesetting %s", (latex) => {
    const protectedLatex = latex
      .replace(/\\/g, PROTECTED_ESCAPE_MARKER)
      .replace(/_/g, PROTECTED_MATH_UNDERSCORE_MARKER)
      .replace(/\*/g, PROTECTED_MATH_STAR_MARKER);
    const html = renderKatexHtml(protectedLatex, { displayMode: true });
    expect(html).toBe(renderKatexHtml(latex, { displayMode: true }));
    expect(html).not.toContain('class="math-fallback"');
  });

  it("falls back for oversized latex instead of hanging", () => {
    const huge = "x".repeat(5000);
    const html = renderKatexHtml(huge, { displayMode: true });
    expect(html).toContain("math-fallback");
    expect(html).not.toContain('class="katex"');
  });

  it("BUG FIX regression: dollar-wrapped fence bodies typeset instead of painting red source", () => {
    // `$...$` inside a ```math fence is not KaTeX syntax. We strip the wrap
    // so KaTeX typesets; leftover `$` used to paint the source in errorColor.
    const html = renderKatexHtml("$x^2$", { displayMode: true });
    expect(html).not.toContain("katex-error");
    expect(html).toContain('class="katex"');
    expect(html).not.toMatch(/\$x\^2\$/);
  });

  it("BUG FIX regression: a KaTeX-unknown command degrades to readable text, not source", () => {
    const html = renderKatexHtml("\\notacommand{x}", { displayMode: true });
    expect(html).not.toContain("katex-error");
    expect(html).toContain("math-fallback");
    expect(html).not.toContain("\\notacommand");
  });
});

describe("buildKatexStaticWebHtml", () => {
  it("measures intrinsic formula content after fonts resize, independent of viewport height", () => {
    const html = buildKatexStaticWebHtml(String.raw`\int_0^1 x^2\,dx=\frac{1}{3}`, { displayMode: true });
    const script = html.match(/<script>([\s\S]*?)<\/script>/i)?.[1];
    expect(script).toBeDefined();
    let contentHeight = 72;
    let resized: (() => void) | undefined;
    const root = { getBoundingClientRect: () => ({ height: contentHeight }), get scrollHeight() { return contentHeight; } };
    const postMessage = jest.fn();
    // Execute only our generated measurement script, with an isolated DOM stub.
    const measure = new Function("document", "window", "ResizeObserver", "setTimeout", script!);
    measure(
      {
        querySelector: () => root,
        documentElement: { scrollHeight: 48 },
        body: { scrollHeight: 48 },
        fonts: { ready: { then: (callback: () => void) => { callback(); return { catch: () => undefined }; } } },
      },
      { ReactNativeWebView: { postMessage }, addEventListener: jest.fn() },
      class {
        constructor(callback: () => void) { resized = callback; }
        observe() {}
      },
      jest.fn(),
    );
    expect(postMessage).toHaveBeenLastCalledWith(JSON.stringify({ h: 74 }));
    contentHeight = 90;
    resized?.();
    expect(postMessage).toHaveBeenLastCalledWith(JSON.stringify({ h: 92 }));
    resized?.();
    expect(postMessage).toHaveBeenCalledTimes(2);
  });

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
