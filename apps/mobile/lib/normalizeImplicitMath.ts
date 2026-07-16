/** Turn model output like `( x^2 = 6 )` or `x2+2=6` into renderable LaTeX. */

const LATEX_CMD = /\\(?:[a-zA-Z]+|.){1,}/;
const MATH_IN_PARENS_RE = /\(\s*([^()\n]{1,180}?)\s*\)/g;
// Triple-backtick fences, LaTeX's own already-delimited display-math spans
// (`$$...$$`, `\[...\]`), AND its inline-math delimiter (`\(...\)`) —
// markdownPreprocess.ts's BLOCK_MATH_RE/BLOCK_MATH_BRACKET_RE convert the
// display forms into ```math fences right after this module runs, and
// splitInlineMath (markdownPreprocess.ts) already recognizes `\(...\)`
// directly as inline math, same as `$...$`. Without protecting `\(...\)`
// here, MATH_IN_PARENS_RE below matches the bare `(`/`)` characters INSIDE
// it (ignoring the leading/trailing backslash as unrelated adjacent text)
// and re-wraps the captured span — which includes that stray trailing
// backslash — in its own `$...$`, corrupting a perfectly valid delimiter
// into e.g. `\$\frac{5}{7}\$`. Any of these spans containing a nested
// LaTeX command (\left, \right, \approx, ...) fares even worse: the later
// wrapInlineLatexCommands heuristic then wraps each stranded command in
// its own separate `$...$`, shattering one expression (e.g.
// `\left(\frac{5}{7}\right)^2`) into disconnected, individually-broken
// fragments with `\left`/`\right` missing the delimiter each requires and
// `^2` left as literal unrendered text outside any math span. So these
// spans get skipped here exactly like a code fence, not touched line-by-line
// by the heuristics below.
const PROTECTED_SPAN_RE = /```[\s\S]*?```|\$\$[\s\S]+?\$\$|\\\[[\s\S]+?\\\]|\\\([\s\S]+?\\\)/g;

// A LaTeX command (\frac, \sqrt, \boxed, ...) embedded mid-sentence with no
// $...$ wrap at all — e.g. "simplifying\frac{8!}{6!}?" — is distinct from
// looksLikeBareEquation's whole-LINE-only heuristic below: there's real
// prose before/after it, so the whole line can't be wrapped, only the
// command span itself.
const INLINE_LATEX_CMD_RE = /\\[a-zA-Z]+/g;

const BARE_EQUATION_RE = /^[0-9a-zA-Z+\-*/^=±√\\_.\s]+$/i;

export function fixImplicitExponents(expr: string): string {
  let s = expr.trim();
  if (!s) return s;

  s = s.replace(/([a-zA-Z])([0-9]+)(?=[+\-=)\]|,\s]|$)/g, "$1^$2");
  s = s.replace(/^(\d)(\d)(?=[+\-*/=])/, "$1^$2");
  s = s.replace(/(\s)(\d)(\d)(?=[+\-*/=])/g, "$1$2^$3");
  if (s.includes("±") && !s.includes("\\pm")) {
    s = s.replace(/±\s*/g, "\\pm ");
  }
  return s.replace(/\s+/g, " ").trim();
}

/** True when a parenthetical looks like English prose, not `(2x-1)` / `(x+3)`. */
function looksLikeProseParenthetical(s: string): boolean {
  // Two or more 3+-letter words → "excluded values", "in disguise", etc.
  // Single short tokens like "sqrt" / variables don't match.
  const words = s.match(/[A-Za-z]{3,}/g) ?? [];
  return words.length >= 2;
}

function isMathLike(inner: string): boolean {
  const s = fixImplicitExponents(inner);
  if (s.length < 2) return false;
  // BARE_EQUATION_RE's char class allows `*` for multiplication, which also
  // matches markdown's `**bold**`/`__bold__` markers — without this guard a
  // prose line like "**Solve** 2^x + 5 = 7" gets misread as a bare equation
  // and wrapped whole in `$...$`, corrupting the bold markdown (the math
  // renderer displays raw source text, not parsed markdown emphasis).
  if (/\*\*|__/.test(s)) return false;
  // Already-delimited math inside the paren must not be re-wrapped — wrapping
  // `(excluded values: $x \neq -3, 2$)` as `$excluded…$x…2$$` invents a
  // trailing `$$` that steals the next display-math opener, leaving equations
  // as raw LaTeX and prose glued into MathBlock fences.
  if (s.includes("$")) return false;
  if (looksLikeProseParenthetical(s)) return false;
  if (LATEX_CMD.test(s)) return true;
  if (/\^|_[{0-9a-zA-Z]/.test(s)) return true;
  if (/[±√∓≤≥≠]|\\pm/.test(s)) return true;
  if (!/[=<>]/.test(s)) return false;
  if (!BARE_EQUATION_RE.test(s)) return false;
  return /[+\-*/^\\=]/.test(s);
}

function looksLikeBareEquation(line: string): boolean {
  const s = fixImplicitExponents(line.trim());
  if (!/=/.test(s)) return false;
  return BARE_EQUATION_RE.test(s) && isMathLike(s);
}

function unwrapParens(expr: string): string {
  const s = expr.trim();
  const m = s.match(/^\(\s*([\s\S]+?)\s*\)$/);
  return m ? m[1].trim() : s;
}

function wrapMath(expr: string): string {
  return `$${fixImplicitExponents(unwrapParens(expr))}$`;
}

/** Index just past any {...} groups immediately following `start` (balanced
 * braces, unlike a naive [^}]+ regex) — e.g. for "\frac{8!}{6!}" starting
 * right after "\frac", returns the index after the closing "}" of "{6!}". */
function skipBraceGroups(s: string, start: number): number {
  let i = start;
  while (s[i] === "{") {
    let depth = 0;
    let j = i;
    for (; j < s.length; j += 1) {
      if (s[j] === "{") depth += 1;
      else if (s[j] === "}") {
        depth -= 1;
        if (depth === 0) {
          j += 1;
          break;
        }
      }
    }
    if (depth !== 0) return i; // unbalanced — stop before the broken group
    i = j;
  }
  return i;
}

/** Wraps a bare LaTeX command (plus its brace groups) in $...$ where it's
 * embedded mid-sentence with no delimiters at all — e.g.
 * "simplifying\frac{8!}{6!}?" — distinct from the whole-line-only
 * looksLikeBareEquation path above, since real prose surrounds it here.
 * Skipped whenever the line already has a "$" anywhere, so it never
 * double-wraps something wrapMath already handled earlier in this line. */
/** Apply `fn` only to the non-`$...$` segments of a line, leaving already-
 * delimited inline math spans untouched. Without this, a heuristic like
 * MATH_IN_PARENS_RE re-wraps parentheticals INSIDE an existing `$...$`
 * (e.g. `$(-2 + \sqrt{3})^2 + 4(-2 + \sqrt{3}) + ...$`), producing `$$` and
 * shattering `$` pairing across the whole message — leaving `\sqrt` as raw
 * text and gluing adjacent prose into the math. */
function applyOutsideInlineMath(line: string, fn: (s: string) => string): string {
  const out: string[] = [];
  let last = 0;
  const re = /\$[^$\n]+?\$/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(line)) !== null) {
    if (m.index > last) out.push(fn(line.slice(last, m.index)));
    out.push(m[0]);
    last = m.index + m[0].length;
  }
  if (last === 0) return fn(line);
  if (last < line.length) out.push(fn(line.slice(last)));
  return out.join("");
}

function wrapInlineLatexCommands(line: string): string {
  if (line.includes("$")) return line;
  INLINE_LATEX_CMD_RE.lastIndex = 0;
  let out = "";
  let last = 0;
  let match: RegExpExecArray | null;
  while ((match = INLINE_LATEX_CMD_RE.exec(line)) !== null) {
    const start = match.index;
    const end = skipBraceGroups(line, INLINE_LATEX_CMD_RE.lastIndex);
    out += line.slice(last, start) + `$${line.slice(start, end)}$`;
    last = end;
    INLINE_LATEX_CMD_RE.lastIndex = end;
  }
  if (last === 0) return line;
  return out + line.slice(last);
}

function normalizeMathLine(line: string): string {
  if (/\]\(https?:\/\//.test(line) || /\[places\s*\n/i.test(line)) {
    return line;
  }
  let out = line;

  const equationLabel = out.match(
    /^(\s*(?:\*\*)?(?:Given\s+)?(?:Equation|equation)(?:\*\*)?\s*:\s*)(.+)$/i,
  );
  if (equationLabel) {
    const expr = equationLabel[2].trim();
    if (isMathLike(expr) || looksLikeBareEquation(expr)) {
      return `${equationLabel[1]}${wrapMath(expr)}`;
    }
  }

  // Any single-letter variable (not just x/y/z — "Let c = 3:", "For n = 5:"
  // are equally common phrasing the model uses for a substitution check).
  const verifyLabel = out.match(
    /^(\s*(?:[-*]\s+)?(?:(?:For|Let)\s+)?[a-zA-Z]\s*=\s*-?\d+\s*:\s*)(.+)$/i,
  );
  if (verifyLabel) {
    const expr = verifyLabel[2].replace(/\s*[✓✔✅]\s*$/u, "").trim();
    if (isMathLike(expr) || looksLikeBareEquation(expr)) {
      const mark = verifyLabel[2].match(/[✓✔✅]\s*$/u)?.[0] ?? "";
      return `${verifyLabel[1]}${wrapMath(expr)}${mark ? ` ${mark.trim()}` : ""}`;
    }
  }

  const trimmed = out.trim();
  if (looksLikeBareEquation(trimmed) && !trimmed.includes("$") && !/^[-*]\s/.test(trimmed)) {
    return out.replace(trimmed, wrapMath(trimmed));
  }

  out = applyOutsideInlineMath(out, (seg) =>
    seg.replace(MATH_IN_PARENS_RE, (full, inner: string) =>
      isMathLike(String(inner)) ? wrapMath(String(inner)) : full,
    ),
  );

  out = wrapInlineLatexCommands(out);

  return out.replace(/^(\s*)\$\-\s*(.+?)\s*\$$/, "$1- $2");
}

export function normalizeImplicitMathInProse(text: string): string {
  return text.split("\n").map(normalizeMathLine).join("\n");
}

export function normalizeImplicitMath(content: string): string {
  const chunks: string[] = [];
  let last = 0;
  let match: RegExpExecArray | null;
  while ((match = PROTECTED_SPAN_RE.exec(content)) !== null) {
    if (match.index > last) {
      chunks.push(normalizeImplicitMathInProse(content.slice(last, match.index)));
    }
    chunks.push(match[0]);
    last = match.index + match[0].length;
  }
  chunks.push(normalizeImplicitMathInProse(content.slice(last)));
  return chunks.join("");
}
