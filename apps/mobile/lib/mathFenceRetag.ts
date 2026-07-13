// Trailing (?=[^a-zA-Z]|$) instead of \b: \b treats `_` as a word char, so it
// would not match the boundary between a command and a subscript
// (`\log_2`, `\lim_{x\to0}`, `\sum_{i=1}^n` are all extremely common LaTeX).
const LATEX_CMD_RE =
  /\\(?:pm|mp|sqrt|frac|text|mathrm|boxed|times|cdot|leq|geq|neq|infty|alpha|beta|gamma|delta|epsilon|zeta|eta|theta|iota|kappa|lambda|mu|nu|xi|omicron|pi|rho|sigma|tau|upsilon|phi|chi|psi|omega|begin|left|right|log|ln|exp|lim|sup|inf|sin|cos|tan|sec|csc|cot|arcsin|arccos|arctan|sinh|cosh|tanh|sum|prod|int|det|gcd|min|max|arg|deg|ker|dim|hom|binom|partial|nabla|vec|hat|bar|dot|overline|underline|Longrightarrow|Rightarrow|longrightarrow|rightarrow|Longleftrightarrow|Leftrightarrow|longleftrightarrow|leftrightarrow|Longleftarrow|Leftarrow|longleftarrow|leftarrow|implies|iff|to|mapsto|longmapsto)(?=[^a-zA-Z]|$)/;

function looksLikeAlgebraLine(line: string): boolean {
  if (!line || line.length > 120) return false;
  if (/^(def |class |import |function |const |let |var |if |for |while )/i.test(line)) {
    return false;
  }
  // `;`/console./print(/=> are real code tells; braces alone are not — LaTeX
  // uses `{}` constantly for grouping (`2^{1}`, `a_{n}`), and a genuine code
  // fence from the model is virtually always explicitly tagged anyway.
  if (/;|console\.|print\(|=>/.test(line)) return false;
  if (/^[a-zA-Z]\^[\d{]/.test(line)) return true;
  if (/=/.test(line) && /[a-zA-Z]\^/.test(line)) return true;
  if (/=/.test(line) && /^[\da-zA-Z+\-*/^=(){}\\_\s.,²³√±]+$/.test(line)) return true;
  return false;
}

/** Plain ``` or ```math body that should render as math, not a code block. */
export function looksLikeMathFenceBody(content: string): boolean {
  const raw = content.trim();
  if (!raw || raw.length > 400) return false;
  if (raw.startsWith("{")) return false;

  // A body that's ENTIRELY wrapped in a redundant $...$/$$...$$ (the model
  // mistaking fence syntax for inline-math syntax) must be classified on
  // what's underneath the wrap — e.g. "$2^x = 2$" has no recognized LaTeX
  // command of its own, so without unwrapping first it fails every check
  // below (the `$` characters also aren't in looksLikeAlgebraLine's allowed
  // character class) and falls through to a plain code block.
  const s = stripRedundantDollarWrap(raw);

  // An unambiguous LaTeX command (\times, \begin, \text{, ...) is a strong
  // enough signal on its own — it must not be gated by the line-count cap
  // below, or a multi-step \begin{aligned}...\end{aligned} derivation
  // (routinely 5+ lines for anything beyond a trivial 2-step solve) gets
  // rejected before this check even runs and falls back to a plain code
  // block. The line cap is only a safety net for the much weaker "every
  // line looks like bare algebra" heuristic further below, which has no
  // such explicit signal to lean on.
  if (LATEX_CMD_RE.test(s)) return true;
  if (/\\text\{/.test(s)) return true;

  const lines = s.split("\n").filter((line) => line.trim());
  if (lines.length > 4) return false;

  if (lines.every((line) => looksLikeAlgebraLine(line.trim()))) {
    return lines.some((line) => /=/.test(line));
  }
  return false;
}

/**
 * A ```math fence body must be bare LaTeX — $...$/$$...$$ are markdown-level
 * inline/display delimiters, not KaTeX syntax, so a model that wraps a fence
 * body in them anyway produces a literal "$" KaTeX can't parse: with
 * throwOnError:false it renders the raw source in errorColor instead of
 * throwing (e.g. "$= \pi \times 16$" showing up in red instead of typeset
 * math). Strip a redundant whole-string wrap defensively rather than let it
 * visibly break.
 */
export function stripRedundantDollarWrap(s: string): string {
  const double = s.match(/^\$\$([\s\S]+)\$\$$/);
  if (double) return double[1].trim();
  const single = s.match(/^\$([^$\n]+)\$$/);
  if (single) return single[1].trim();
  return s;
}

/**
 * The model sometimes wraps only individual sub-expressions in $...$ within
 * an otherwise-bare fence body — e.g. "n! = n $\times$ (n-1)!" — rather than
 * the whole body, which stripRedundantDollarWrap's whole-string match above
 * doesn't catch. Any matched $...$/$$...$$ pair anywhere in a fence body is
 * invalid (same "bare LaTeX only" contract), so unwrap every one of them,
 * leaving an unmatched lone "$" (e.g. real currency text) untouched.
 */
export function stripEmbeddedDollarWraps(s: string): string {
  if (!s.includes("$")) return s;
  return s.replace(/\$\$([^$\n]+?)\$\$|\$([^$\n]+?)\$/g, (_m, double, single) => double ?? single);
}

/** Model often emits ```latex — detect and reroute at render time. */
export function looksLikeLatexFence(content: string): boolean {
  return looksLikeMathFenceBody(content);
}

/**
 * Rewrite model math fences before markdown parse (latex/plain → math only).
 *
 * Matches every fence (tagged or not) in a single pass, so an already-tagged
 * fence's own closing ``` is always consumed as part of ITS match, never
 * mistaken for the opener of a new bare fence — a bare-fence-only regex here
 * previously matched a tagged fence's closing ``` as an opener, silently
 * swallowing everything up to the next fence as a single bogus "math" block.
 */
export function retagMathAndDiagramFences(content: string): string {
  let out = content;

  out = out.replace(
    /```(?:latex|tex)\s*\n([\s\S]*?)```/gi,
    (_m, body: string) => `\`\`\`math\n${body.trim()}\n\`\`\``,
  );

  out = out.replace(/```([^\n]*)\n([\s\S]*?)```/g, (full, info: string, body: string) => {
    if (info.trim()) return full;
    const trimmed = body.trim();
    if (looksLikeMathFenceBody(trimmed)) {
      return `\`\`\`math\n${trimmed}\n\`\`\``;
    }
    return full;
  });

  return out;
}
