/** LaTeX → self-contained HTML for sandboxed WebView math preview. */

import { buildKatexStaticWebHtml } from "@/lib/katexRender";
import { injectPreviewCsp, MATH_PREVIEW_CSP } from "@/lib/previewSandbox";

export type MathEngine = "katex" | "mathjax";

const HEAVY_MATH_RE =
  /\\begin\{(matrix|pmatrix|bmatrix|vmatrix|Vmatrix|Bmatrix|align\*?|aligned|gathered|cases|array|split|multline|eqnarray)\}|\\(?:frac|int|iint|iiint|sum|prod|lim|binom|overset|underset|stackrel|displaystyle|xrightarrow|xleftarrow)(?=[\s_^\\{])|\\sqrt\s*\[/i;

export function isHeavyMath(latex: string): boolean {
  const trimmed = latex.trim();
  if (!trimmed) return false;
  if (trimmed.length > 96) return true;
  if (trimmed.includes("\n")) return true;
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
</style>
</head>
<body>
<div id="out"></div>
<div id="err"></div>
<script>
  window.MathJax = {
    loader: { load: ["[tex]/ams", "[tex]/noerrors", "[tex]/noundefined"] },
    tex: {
      packages: { "[+]": ["ams", "noerrors", "noundefined"] },
      inlineMath: [],
      displayMath: [],
    },
    startup: {
      ready() {
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
<script async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js"></script>
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
