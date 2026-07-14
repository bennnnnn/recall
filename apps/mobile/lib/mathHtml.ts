/** LaTeX → self-contained HTML for sandboxed WebView math preview. */

import { buildKatexStaticWebHtml } from "@/lib/katexRender";
import { injectPreviewCsp, MATH_PREVIEW_CSP } from "@/lib/previewSandbox";

export type MathEngine = "katex" | "mathjax";

// Empirically verified against the bundled KaTeX 0.17.0 (katexRender.ts):
// frac/int/iint/iiint/sum/prod/binom/lim/overset/underset/stackrel/
// displaystyle/xrightarrow/xleftarrow/sqrt[n]{} and every matrix/aligned/
// align*/cases/array/gathered/split environment all render correctly under
// katex.renderToString with throwOnError:true — none of them need MathJax.
// Only `multline` and `eqnarray` genuinely aren't implemented by KaTeX
// ("No such environment"). Routing the rest to MathJax was unnecessary
// MathJax-CDN exposure (the single biggest offline-rendering failure mode).
const HEAVY_MATH_RE = /\\begin\{(multline|eqnarray)\}/i;

export function isHeavyMath(latex: string): boolean {
  const trimmed = latex.trim();
  if (!trimmed) return false;
  // Length and newlines alone used to also route here — but a multi-step
  // \begin{aligned}...\end{aligned} derivation is exactly the kind of
  // content that's long AND multi-line, and per the verification above it
  // renders correctly under local, bundled KaTeX. Routing it to MathJax's
  // CDN instead means it never renders at all when that CDN is unreachable
  // (blank box, only the 8s-per-block fallback as a safety net) — routing
  // it to KaTeX renders it immediately, fully offline, every time.
  return HEAVY_MATH_RE.test(trimmed);
}

export function pickMathEngine(latex: string): MathEngine {
  return isHeavyMath(latex) ? "mathjax" : "katex";
}

export function escapeForHtmlTemplate(value: string): string {
  return value
    .replace(/\\/g, "\\\\")
    .replace(/`/g, "\\`")
    .replace(/\$/g, "\\$")
    .replace(/<\/script>/gi, "<\\/script>");
}

export type MathHtmlOptions = {
  displayMode: boolean;
  engine?: MathEngine;
  textColor: string;
  bgColor: string;
  errorColor?: string;
  compact?: boolean;
};

export function buildMathWebHtml(latex: string, options: MathHtmlOptions): string {
  const engine = options.engine ?? pickMathEngine(latex);

  if (engine === "mathjax") {
    const safeLatex = escapeForHtmlTemplate(latex.trim());
    const display = options.displayMode ? "true" : "false";
    const pad = options.compact ? "0" : "12px 14px";
    const errorColor = options.errorColor ?? "#EF4444";

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
        MathJax.tex2chtmlPromise(latex, { display: ${display} })
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
<script async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js" onerror="showMathJaxFallback()"></script>
</body>
</html>`, MATH_PREVIEW_CSP);
  }

  return buildKatexStaticWebHtml(latex.trim(), {
    displayMode: options.displayMode,
    textColor: options.textColor,
    bgColor: options.bgColor,
    compact: options.compact,
  });
}
