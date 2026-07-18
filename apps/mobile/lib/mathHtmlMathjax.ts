/** MathJax HTML builder — kept in its own module so Metro can async-split
 * the ~2MB tex-svg vendor off the chat / KaTeX cold path. Only loaded when
 * `pickMathEngine` routes to mathjax (multline / eqnarray). */

import { escapeForHtmlTemplate, type MathHtmlOptions } from "@/lib/mathHtml";
import { injectPreviewCsp, MATH_PREVIEW_CSP, inlineScript } from "@/lib/previewSandbox";
import { MATHJAX_TEX_SVG_JS } from "@/lib/vendor/mathjaxTexSvgJs";

export function buildMathjaxWebHtml(latex: string, options: MathHtmlOptions): string {
  const safeLatex = escapeForHtmlTemplate(latex.trim());
  const display = options.displayMode ? "true" : "false";
  const pad = options.compact ? "0" : "12px 14px";
  // Prefer theme.danger from callers; keep a mode-agnostic CSS red as last resort
  // (not lightTheme.danger — that reads wrong on dark HTML backgrounds).
  const errorColor = options.errorColor ?? "currentColor";

  return injectPreviewCsp(`<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<style>
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; background: ${options.bgColor}; }
  body {
    color: ${options.textColor};
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    padding: ${pad};
    overflow-x: auto;
    overflow-y: hidden;
  }
  #out { display: ${options.displayMode ? "block" : "inline-block"}; max-width: 100%; }
  #out mjx-container { color: ${options.textColor} !important; }
  #err { display: none; color: ${errorColor}; font-size: 13px; white-space: pre-wrap; word-break: break-word; font-family: ui-monospace, monospace; }
  #fallback { display: none; }
  #fallback .badge { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.4px; color: ${options.textColor}; opacity: 0.7; margin-bottom: 4px; }
  #fallback .latex { font-family: ui-monospace, monospace; font-size: 14px; white-space: pre-wrap; word-break: break-word; }
  #fallback .hint { font-size: 12px; opacity: 0.6; margin-top: 4px; }
</style>
</head>
<body>
<div id="out"></div>
<div id="err"></div>
<div id="fallback">
  <div class="badge">MathJax preview</div>
  <div class="latex" id="fallback-latex"></div>
  <div class="hint">Rendering failed — showing raw source.</div>
</div>
<script>
  var mathJaxFallbackShown = false;
  function showMathJaxFallback() {
    if (mathJaxFallbackShown) return;
    mathJaxFallbackShown = true;
    clearTimeout(mathJaxLoadTimeout);
    document.getElementById("out").style.display = "none";
    document.getElementById("fallback-latex").textContent = \`${safeLatex}\`;
    document.getElementById("fallback").style.display = "block";
    postHeight();
  }
  // CDN script has no built-in load signal beyond onerror (which only fires
  // for a hard network/404 failure, not a hang) — a load-timeout race is the
  // only way to catch a stalled fetch and avoid a silently blank box offline.
  // (Now that the bundle is inlined, this guards against a pathological init
  // hang rather than a network stall — kept as a safety net.)
  var mathJaxLoadTimeout = setTimeout(showMathJaxFallback, 8000);
  window.MathJax = {
    loader: { load: ["[tex]/ams", "[tex]/noerrors", "[tex]/noundefined"] },
    tex: {
      packages: { "[+]": ["ams", "noerrors", "noundefined"] },
      inlineMath: [],
      displayMath: [],
    },
    startup: {
      ready() {
        clearTimeout(mathJaxLoadTimeout);
        MathJax.startup.defaultReady();
        const latex = \`${safeLatex}\`;
        MathJax.tex2svgPromise(latex, { display: ${display} })
          .then(function(node) {
            document.getElementById("out").appendChild(node);
            postHeight();
          })
          .catch(function(err) {
            document.getElementById("err").textContent = err && err.message ? err.message : String(err);
            document.getElementById("err").style.display = "block";
            postHeight();
          });
      },
    },
  };
  function postHeight() {
    const h = Math.ceil(document.documentElement.scrollHeight || document.body.scrollHeight || 40);
    if (window.ReactNativeWebView) {
      window.ReactNativeWebView.postMessage(JSON.stringify({ h: h }));
    }
  }
</script>
<script>${inlineScript(MATHJAX_TEX_SVG_JS)}</script>
</body>
</html>`, MATH_PREVIEW_CSP);
}
