/** LaTeX → self-contained HTML for sandboxed WebView math preview.
 *
 * KaTeX (common path) stays sync here. MathJax (~2MB tex-svg) lives in
 * `mathHtmlMathjax.ts` and is loaded via dynamic `import()` only when
 * `pickMathEngine` returns "mathjax" — keeps it off the chat cold start. */

import { buildKatexStaticWebHtml } from "@/lib/katexRender";

export type MathEngine = "katex" | "mathjax";

// Empirically verified against the bundled KaTeX 0.17.0 (katexRender.ts):
// frac/int/iint/iiint/sum/prod/binom/lim/overset/underset/stackrel/
// displaystyle/xrightarrow/xleftarrow/sqrt[n]{} and every matrix/aligned/
// align*/cases/array/gathered/split environment all render correctly under
// katex.renderToString with throwOnError:true — none of them need MathJax.
// Only `multline` and `eqnarray` genuinely aren't implemented by KaTeX
// ("No such environment"). Routing the rest to MathJax was unnecessary
// weight. MathJax (tex-svg, vendored inline) is reserved for those two
// environments; KaTeX handles everything else with no JS parse cost per block.
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

/** Sync KaTeX HTML only. For MathJax, use `buildMathjaxWebHtml` (async chunk). */
export function buildMathWebHtml(latex: string, options: MathHtmlOptions): string {
  const engine = options.engine ?? pickMathEngine(latex);
  if (engine === "mathjax") {
    throw new Error(
      "MathJax HTML is built via mathHtmlMathjax (async chunk). Use buildMathjaxWebHtml.",
    );
  }

  return buildKatexStaticWebHtml(latex.trim(), {
    displayMode: options.displayMode,
    textColor: options.textColor,
    bgColor: options.bgColor,
    compact: options.compact,
  });
}
