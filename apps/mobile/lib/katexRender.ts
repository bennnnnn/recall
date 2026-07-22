import katex from "katex";

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
  const trimmed = latex.trim();
  if (!trimmed) return "";

  let body = "";
  try {
    if (trimmed.length > MAX_KATEX_CHARS) {
      body = `<code>${escapeHtml(trimmed.slice(0, 200))}…</code>`;
    } else {
      body = katex.renderToString(trimmed, {
        throwOnError: false,
        displayMode: options.displayMode ?? false,
        strict: "ignore",
        output: "html",
        maxSize: KATEX_MAX_SIZE,
        maxExpand: KATEX_MAX_EXPAND,
      });
    }
  } catch {
    body = `<code>${escapeHtml(trimmed)}</code>`;
  }

  const pad = options.compact ? "0" : "10px 12px";
  const align = options.displayMode ? "center" : "left";
  const bg = options.bgColor ?? "transparent";
  const color = options.textColor ?? "inherit";

  return `<div><style>${KATEX_CSS}
.math-root{padding:${pad};background:${bg};color:${color};overflow:hidden;max-width:100%;}
.katex{color:${color};}
.math-wrap{display:flex;justify-content:${align};align-items:center;max-width:100%;overflow-x:auto;}
</style><div class="math-root"><div class="math-wrap">${body}</div></div></div>`;
}

/** Pre-rendered KaTeX in a WebView — real browser layout, not RenderHtml. */
export function buildKatexStaticWebHtml(
  latex: string,
  options: KatexRenderOptions = {},
): string {
  const inner = renderKatexHtml(latex, options);
  const justify = options.displayMode ? "center" : "flex-start";

  return injectPreviewCsp(`<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<style>
  html, body { margin: 0; padding: 0; background: transparent; overflow: hidden; }
  body { display: flex; align-items: center; justify-content: ${justify}; }
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

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
