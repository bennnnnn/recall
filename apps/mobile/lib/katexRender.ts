import katex from "katex";

import { readableLatexFallback } from "@/lib/mathText";
import { stripEmbeddedDollarWraps, stripRedundantDollarWrap } from "@/lib/mathFenceRetag";
import { KATEX_CSS } from "@/lib/vendor/katexCss";
import { injectPreviewCsp } from "@/lib/previewSandbox";

/** Cap pathological model latex before KaTeX can hang the JS thread. */
const MAX_KATEX_CHARS = 4000;
const KATEX_MAX_SIZE = 20;
const KATEX_MAX_EXPAND = 500;

export type KatexRenderOptions = {
  displayMode?: boolean;
  textColor?: string;
  bgColor?: string;
  compact?: boolean;
};

export function renderKatexHtml(latex: string, options: KatexRenderOptions = {}): string {
  const trimmed = stripEmbeddedDollarWraps(stripRedundantDollarWrap(latex.trim()));
  if (!trimmed) return "";

  let body = "";
  try {
    if (trimmed.length > MAX_KATEX_CHARS) {
      body = fallbackHtml(trimmed);
    } else {
      body = katex.renderToString(trimmed, {
        throwOnError: true,
        displayMode: options.displayMode ?? false,
        strict: "ignore",
        output: "html",
        maxSize: KATEX_MAX_SIZE,
        maxExpand: KATEX_MAX_EXPAND,
      });
    }
  } catch {
    body = fallbackHtml(trimmed);
  }

  const pad = options.compact
    ? "0"
    : options.displayMode
      ? "8px 4px"
      : "4px 2px";
  const align = options.displayMode ? "center" : "left";
  const bg = options.bgColor ?? "transparent";
  const color = options.textColor ?? "inherit";
  const displayMargin = options.displayMode && !options.compact ? "0.6em 0" : "0";

  // Scrollable wide formulas: inner is at least full width (centers short
  // display math) but grows with content so long expressions aren't clipped
  // — the outer scroller is what the user pans horizontally.
  return `<div><style>${KATEX_CSS}
.math-root{padding:${pad};background:${bg};color:${color};max-width:100%;overflow-x:auto;overflow-y:hidden;-webkit-overflow-scrolling:touch;}
.katex{color:${color};}
.math-wrap{display:flex;justify-content:${align};align-items:center;min-width:100%;width:max-content;box-sizing:border-box;}
.katex-display{margin:${displayMargin};}
</style><div class="math-root"><div class="math-wrap">${body}</div></div></div>`;
}

/** Pre-rendered KaTeX in a WebView — real browser layout, not RenderHtml. */
export function buildKatexStaticWebHtml(
  latex: string,
  options: KatexRenderOptions = {},
): string {
  const inner = renderKatexHtml(latex, options);

  return injectPreviewCsp(`<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<style>
  html, body { margin: 0; padding: 0; background: transparent; overflow-x: auto; overflow-y: hidden; }
  body { display: block; max-width: 100%; }
</style>
</head>
<body>
${inner}
<script>
(function () {
  function postHeight() {
    var h = Math.ceil(document.documentElement.scrollHeight || document.body.scrollHeight || 24);
    if (window.ReactNativeWebView) {
      window.ReactNativeWebView.postMessage(JSON.stringify({ h: h }));
    }
  }
  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(postHeight).catch(postHeight);
  } else {
    setTimeout(postHeight, 40);
  }
  // One late settle for CDN font swap — avoid the old 40/250/800 triple-post
  // which resized the chat bubble three times and looked like shaking.
  setTimeout(postHeight, 300);
})();
</script>
</body>
</html>`);
}

function fallbackHtml(latex: string): string {
  return `<span class="math-fallback">${escapeHtml(readableLatexFallback(latex))}</span>`;
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
