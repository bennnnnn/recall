// Trailing (?=[^a-zA-Z]|$) instead of \b: \b treats `_` as a word char, so it
// would not match the boundary between a command and a subscript
// (`\log_2`, `\lim_{x\to0}`, `\sum_{i=1}^n` are all extremely common LaTeX).
const LATEX_CMD_RE =
  /\\(?:pm|mp|sqrt|frac|text|mathrm|boxed|times|cdots|ldots|dots|cdot|leq|geq|neq|infty|alpha|beta|gamma|delta|epsilon|zeta|eta|theta|iota|kappa|lambda|mu|nu|xi|omicron|pi|rho|sigma|tau|upsilon|phi|chi|psi|omega|begin|left|right|langle|rangle|lvert|rvert|lVert|rVert|log|ln|exp|lim|sup|inf|sin|cos|tan|sec|csc|cot|arcsin|arccos|arctan|sinh|cosh|tanh|sum|prod|int|det|gcd|min|max|arg|deg|ker|dim|hom|binom|partial|nabla|vec|hat|bar|dot|overline|underline|Longrightarrow|Rightarrow|longrightarrow|rightarrow|Longleftrightarrow|Leftrightarrow|longleftrightarrow|leftrightarrow|Longleftarrow|Leftarrow|longleftarrow|leftarrow|implies|iff|to|mapsto|longmapsto|lor|vee|land|wedge|mathbb|operatorname|approx|equiv|propto|angle|degree|cup|cap|subset|supset|forall|exists|notin|in)(?=[^a-zA-Z]|$)/;

/** LaTeX spacing (`\;` `\,` `\:` `\!` `\quad`) — not a C `;` statement. */
const LATEX_SPACING_RE = /\\[;,:!]|\\(?:quad|qquad)(?=[^a-zA-Z]|$)/;

/** Normalize spacing cmds so algebra heuristics don't see literal `;`. */
function stripLatexSpacing(s: string): string {
  return s.replace(LATEX_SPACING_RE, " ");
}

function looksLikeAlgebraLine(line: string): boolean {
  if (!line || line.length > 120) return false;
  if (/^(def |class |import |function |const |let |var |if |for |while )/i.test(line)) {
    return false;
  }
  // `;`/console./print(/=> are real code tells — but `\;` is LaTeX thin space,
  // so strip spacing commands before treating `;` as a statement terminator.
  const forCodeCheck = stripLatexSpacing(line);
  if (/;|console\.|print\(|=>/.test(forCodeCheck)) return false;
  if (/^[a-zA-Z]\^[\d{]/.test(line)) return true;
  if (/=/.test(line) && /[a-zA-Z]\^/.test(line)) return true;
  // Digits, letters, ops, factorial (!), unicode math (× ÷ → …), LaTeX cmds.
  // Allow `;` only as part of already-stripped spacing (check normalized form).
  if (
    /=/.test(line) &&
    /^[\da-zA-Z+\-*/^=(){}\\_!\s.,²³√±×÷·⋅→←↔⇒⇔∞πθ∑∏]+$/.test(forCodeCheck)
  ) {
    return true;
  }
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
  // Spacing-only arithmetic (e.g. `20 \;-\; 10 \;=\; 10`) has no named
  // command from LATEX_CMD_RE — without this, the `;` inside `\;` made the
  // algebra heuristic reject it as "code" and the Copy box showed raw LaTeX.
  if (LATEX_SPACING_RE.test(s) && /=/.test(s) && /[\d]/.test(s)) return true;

  const lines = s.split("\n").filter((line) => line.trim());
  // A multi-step derivation written as bare algebra (one equation per line,
  // no LaTeX commands) routinely runs 5+ lines — e.g. a 5-step solve or a
  // system of 3 equations. The old cap of 4 rejected those and fell through
  // to a plain code block. Raise the cap to 12 for the algebra-only path;
  // the LATEX_CMD_RE check above already handles command-bearing bodies of
  // any length, so this only affects the weaker "every line is bare algebra"
  // heuristic, where 12 is still a reasonable safety net against prose.
  if (lines.length > 12) return false;

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
 * True when inline `$...$` math contains a LaTeX environment
 * (`\begin{matrix}`, `\begin{cases}`, `\begin{aligned}`, `array`, `gathered`,
 * `split`, `bmatrix`/`pmatrix`/`vmatrix`, …) that the native `MathText`
 * renderer can't lay out — those need the KaTeX WebView. Everything else
 * (fractions, `\sqrt`, `\mathbb`, accents, Greek, …) is handled natively and
 * stays inline; only environments route to the block-inline WebView chip.
 */
export function isHeavyInlineMath(latex: string): boolean {
  return /\\begin\{[\w*]+\}/.test(latex);
}

const INLINE_MATH_FENCE_MAX = 48;

/**
 * Short one-line ```math (or untagged algebra) belongs in the sentence as
 * `$...$`, not a gray card. Display environments and multi-line derivations
 * stay block fences.
 */
export function shouldRenderMathFenceInline(body: string): boolean {
  const t = stripRedundantDollarWrap(body.trim());
  if (!t || t.includes("\n")) return false;
  if (t.length > INLINE_MATH_FENCE_MAX) return false;
  if (/\\begin\{/.test(t)) return false;
  if (/[=\\]/.test(t) && !/^\d+\s*[+\-*/]\s*[A-Za-z]$/.test(t)) return false;
  if (/^[A-Za-z]$/.test(t)) return true;
  if (/^\d+\s*[+\-*/]\s*[A-Za-z]$/.test(t)) return true;
  if (/^[A-Za-z]\s*[+\-*/]\s*\d+$/.test(t)) return true;
  return false;
}

/**
 * Rewrite model math fences before markdown parse (latex/plain → math only).
 *
 * Uses a line-by-line scanner instead of a regex, so a fence body that
 * contains nested ``` lines (e.g. a ```markdown fence wrapping a ```latex
 * example) doesn't break the match — the scanner tracks fence depth and
 * only retags top-level fences, never inner fences that belong to an
 * outer fence's body.
 */
export function retagMathAndDiagramFences(content: string): string {
  const lines = content.split("\n");
  const out: string[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i]!;
    // A fence opener is ``` at the start of a line (possibly with an info
    // string after it). Lines that don't start with ``` pass through.
    if (!line.startsWith("```")) {
      out.push(line);
      i += 1;
      continue;
    }

    const info = line.slice(3).trim();

    // Find the matching closer by scanning forward. In standard markdown,
    // fences don't nest — a ``` inside a fence is literal text. But the
    // model sometimes emits nested fences, so we track depth: a line
    // starting with ``` that has a non-empty info string is an opener;
    // a bare ``` (or ``` with only whitespace after it) is a closer.
    let depth = 0;
    let end = -1;
    for (let j = i + 1; j < lines.length; j += 1) {
      const inner = lines[j]!;
      if (inner.startsWith("```")) {
        const innerInfo = inner.slice(3).trim();
        if (innerInfo && depth === 0) {
          // Nested opener inside the body — track depth so we don't treat
          // its closer as OUR closer.
          depth += 1;
        } else if (innerInfo && depth > 0) {
          depth += 1;
        } else {
          // Bare ``` — this is a closer. Decrement depth first if nested.
          if (depth > 0) {
            depth -= 1;
          } else {
            end = j;
            break;
          }
        }
      }
    }

    if (end === -1) {
      // No closer found — pass through unchanged.
      out.push(line);
      i += 1;
      continue;
    }

    const body = lines.slice(i + 1, end).join("\n");
    const bodyTrimmed = body.trim();

    // Tagged latex/tex → math
    if (/^(latex|tex)$/i.test(info)) {
      out.push("```math");
      out.push(bodyTrimmed);
      out.push("```");
      i = end + 1;
      continue;
    }

    // Untagged fence → retag to math if the body looks like math
    if (!info && bodyTrimmed && looksLikeMathFenceBody(bodyTrimmed)) {
      out.push("```math");
      out.push(bodyTrimmed);
      out.push("```");
      i = end + 1;
      continue;
    }

    // Other tagged fence (python, mermaid, …) — keep as-is, including body
    // and closer. The scanner already skipped past nested ``` inside the
    // body, so this preserves the full fence intact.
    for (let j = i; j <= end; j += 1) out.push(lines[j]!);
    i = end + 1;
  }

  return out.join("\n");
}
