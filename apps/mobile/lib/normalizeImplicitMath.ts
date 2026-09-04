/** Turn model output like `( x^2 = 6 )` into renderable LaTeX. Bare `12+3`
 * and identifiers like `x2` are typeset as supplied — exponents are not invented. */

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

// `{` `}` / `[` `]` / `()` / `!` so `3^{\frac{2}{3}}` and `\sqrt[3]{9}` and
// `8!` still count as a bare equation. `*` stays for multiplication (bold is
// rejected separately in isMathLike).
const BARE_EQUATION_RE = /^[0-9a-zA-Z+\-*/^=±√\\_.{}[\]()!\s]+$/i;

/**
 * Display-path cleanup only: unicode ± → `\pm`, collapse runs of spaces.
 * Does **not** invent exponents. Adjacent digits (`12+3`) and letter+digit
 * identifiers (`x2`) stay as written — `x^2` is already typesettable.
 * Composer keypad OCR (`x2` → `x^2`) lives in `applyImplicitPowerNotation`.
 */
export function fixImplicitExponents(expr: string): string {
  let s = expr.trim();
  if (!s) return s;
  if (s.includes("±") && !s.includes("\\pm")) {
    s = s.replace(/±\s*/g, "\\pm ");
  }
  return s.replace(/\s+/g, " ").trim();
}

/**
 * Keypad-only OCR shorthand: a bare variable + digits → exponent (`x2` → `x^2`).
 * Not used on model replies or MathText — `x2` is an identifier there.
 * The lookbehind skips command tails (`\pm2` must not become `\pm^2`).
 */
export function applyImplicitPowerNotation(expr: string): string {
  const s = expr.trim();
  if (!s) return s;
  return s.replace(/(?<!\\[a-zA-Z]*)([a-zA-Z])([0-9]+)(?=[+\-=)\]|,\s]|$)/g, "$1^$2");
}

/** True when a parenthetical looks like English prose, not `(2x-1)` / `(x+3)`. */
function looksLikeProseParenthetical(s: string): boolean {
  // Strip LaTeX command names first — otherwise `\neq` / `\frac` / `\div`
  // contribute letter-runs ("neq", "frac") that look like English words and
  // block wrapping of real math like `(since m \neq 0)` or nested-frac
  // parentheticals that contain several `\frac`s.
  const withoutCmds = s.replace(/\\[a-zA-Z]+/g, " ");
  // Two or more 3+-letter words → "excluded values", "in disguise", etc.
  // Single short tokens like "sqrt" / variables don't match.
  const words = withoutCmds.match(/[A-Za-z]{3,}/g) ?? [];
  return words.length >= 2;
}

export function isMathLike(inner: string): boolean {
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

const MATH_LINE_WORDS =
  /^(sin|cos|tan|sec|csc|cot|log|ln|lg|exp|lim|max|min|gcd|lcm|det|abs|mod|arg|erf|or|and|if|iff|vs)$/i;

function looksLikeBareEquation(line: string): boolean {
  const s = fixImplicitExponents(line.trim());
  if (!/=/.test(s)) return false;
  if (!BARE_EQUATION_RE.test(s) || !isMathLike(s)) return false;
  // Strip command names first — otherwise `\cdot` / `\frac` contribute
  // "cdot"/"frac" letter-runs that fail MATH_LINE_WORDS and block wrapping
  // a real equation like `1\cdot x = 2 - 3^{\frac{2}{3}}`.
  const withoutCmds = s.replace(/\\[a-zA-Z]+/g, " ");
  // "So r + 1/r = 17/4" used to wrap including "So" → MathText painted "Sor".
  const words = withoutCmds.match(/[A-Za-z]{2,}/g) ?? [];
  return words.every((w) => MATH_LINE_WORDS.test(w));
}

function unwrapParens(expr: string): string {
  const s = expr.trim();
  const m = s.match(/^\(\s*([\s\S]+?)\s*\)$/);
  return m ? m[1].trim() : s;
}

function wrapMath(expr: string, format?: (expr: string) => string): string {
  const body = format ? format(unwrapParens(expr)) : fixImplicitExponents(unwrapParens(expr));
  return `$${body}$`;
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

/** Optional `[...]` args (`\sqrt[3]{9}`) immediately after a command name. */
function skipOptionalBrackets(s: string, start: number): number {
  let i = start;
  while (s[i] === " ") i += 1;
  if (s[i] !== "[") return i;
  let depth = 0;
  for (let j = i; j < s.length; j += 1) {
    if (s[j] === "[") depth += 1;
    else if (s[j] === "]") {
      depth -= 1;
      if (depth === 0) return j + 1;
    }
  }
  return i;
}

function skipLatexCommandArgs(s: string, start: number): number {
  return skipBraceGroups(s, skipOptionalBrackets(s, start));
}

const LIST_MARKER_RE = /^(?:\s*(?:[-*•]|\d+[.)])\s+)/;

function listMarkerEnd(seg: string): number {
  const m = LIST_MARKER_RE.exec(seg);
  return m ? m[0].length : 0;
}

/** Walk right from `i` over one math token; null if the next char is prose. */
function consumeMathRight(seg: string, i: number): number | null {
  if (i >= seg.length) return null;
  const c = seg[i] ?? "";
  if (c === " " || c === "\t") return i + 1;
  if (c === "\\") {
    const rest = seg.slice(i + 1);
    const cmd = rest.match(/^[a-zA-Z]+/);
    if (cmd) return skipLatexCommandArgs(seg, i + 1 + cmd[0].length);
    if (rest.length > 0) return i + 2;
    return i + 1;
  }
  if (c === "{") {
    const next = skipBraceGroups(seg, i);
    return next > i ? next : null;
  }
  if (c === "[") {
    const next = skipOptionalBrackets(seg, i);
    return next > i ? next : null;
  }
  if (c === ".") {
    if (/\d/.test(seg[i - 1] ?? "") && /\d/.test(seg[i + 1] ?? "")) return i + 1;
    return null;
  }
  if (/[0-9+\-=^_})\]()|!]/.test(c) || c === "/") return i + 1;
  if (/[a-zA-Z]/.test(c)) {
    const m = seg.slice(i).match(/^[a-zA-Z]+/);
    if (!m || m[0].length > 1) return null;
    return i + 1;
  }
  return null;
}

function expandMathIslandRight(seg: string, start: number): number {
  let i = start;
  let lastNonSpace = start;
  while (true) {
    const next = consumeMathRight(seg, i);
    if (next == null || next <= i) break;
    const ch = seg[i] ?? "";
    if (ch !== " " && ch !== "\t") lastNonSpace = next;
    i = next;
  }
  return lastNonSpace;
}

function expandMathIslandLeft(seg: string, start: number): number {
  const min = listMarkerEnd(seg);
  let i = start;
  while (i > min) {
    const c = seg[i - 1] ?? "";
    if (c === " " || c === "\t") {
      i -= 1;
      continue;
    }
    if (c === "\\") {
      i -= 1;
      continue;
    }
    if (c === ".") {
      if (/\d/.test(seg[i] ?? "") && /\d/.test(seg[i - 2] ?? "")) {
        i -= 1;
        continue;
      }
      break;
    }
    if (/[0-9+\-=^_{}[\]()|!/]/.test(c)) {
      i -= 1;
      continue;
    }
    if (/[a-zA-Z]/.test(c)) {
      let runStart = i - 1;
      while (runStart > min && /[a-zA-Z]/.test(seg[runStart - 1] ?? "")) {
        runStart -= 1;
      }
      const run = seg.slice(runStart, i);
      const afterBs = runStart > min && seg[runStart - 1] === "\\";
      if (afterBs || run.length <= 1) {
        i = afterBs ? runStart - 1 : runStart;
        continue;
      }
      break;
    }
    break;
  }
  while (i < start && (seg[i] === " " || seg[i] === "\t")) i += 1;
  return i;
}

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

/** Wrap a bare LaTeX command (plus its brace groups) in $...$ — e.g.
 * "simplifying\frac{8!}{6!}?" — distinct from the whole-line-only
 * looksLikeBareEquation path, since real prose surrounds it here. */
function wrapInlineLatexCommandsInSegment(seg: string): string {
  INLINE_LATEX_CMD_RE.lastIndex = 0;
  let out = "";
  let last = 0;
  let match: RegExpExecArray | null;
  while ((match = INLINE_LATEX_CMD_RE.exec(seg)) !== null) {
    if (match.index < last) {
      INLINE_LATEX_CMD_RE.lastIndex = last;
      continue;
    }
    const cmdEnd = skipLatexCommandArgs(seg, INLINE_LATEX_CMD_RE.lastIndex);
    // Wrap the whole island (`3^{\frac{2}{3}}`, `1\cdot x = …`) — wrapping
    // only the command shatters `3^{$\frac{2}{3}$}` and leaves `^{` `}` raw.
    const start = expandMathIslandLeft(seg, match.index);
    const end = expandMathIslandRight(seg, cmdEnd);
    out += seg.slice(last, start) + `$${seg.slice(start, end)}$`;
    last = end;
    INLINE_LATEX_CMD_RE.lastIndex = end;
  }
  if (last === 0) return seg;
  return out + seg.slice(last);
}

/** Wrap bare LaTeX commands only outside existing `$...$` spans — so a mixed
 * line like `Cancel $\frac{m}{m}$ (since m \neq 0)` still wraps the leftover
 * `\neq` instead of bailing because the line already contains `$`. */
function wrapInlineLatexCommands(line: string): string {
  return applyOutsideInlineMath(line, wrapInlineLatexCommandsInSegment);
}

function normalizeMathLine(line: string, format?: (expr: string) => string): string {
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
      return `${equationLabel[1]}${wrapMath(expr, format)}`;
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
      return `${verifyLabel[1]}${wrapMath(expr, format)}${mark ? ` ${mark.trim()}` : ""}`;
    }
  }

  const discourseLead = out.match(
    /^(\s*(?:So|Thus|Hence|Then|Therefore|Now|Also|Finally|And|But),?\s+)(.+)$/i,
  );
  if (discourseLead) {
    const expr = discourseLead[2].trim();
    if (looksLikeBareEquation(expr) || isMathLike(expr)) {
      return `${discourseLead[1]}${wrapMath(expr, format)}`;
    }
  }

  const listLead = out.match(/^(\s*(?:[-*•]|\d+[.)])\s+)(.*)$/);
  if (listLead && !listLead[2].includes("$")) {
    const expr = listLead[2].trim();
    if (looksLikeBareEquation(expr)) {
      return `${listLead[1]}${wrapMath(expr, format)}`;
    }
  }

  const trimmed = out.trim();
  if (looksLikeBareEquation(trimmed) && !trimmed.includes("$") && !/^[-*•]\s/.test(trimmed)) {
    return out.replace(trimmed, wrapMath(trimmed, format));
  }

  out = applyOutsideInlineMath(out, (seg) =>
    seg.replace(MATH_IN_PARENS_RE, (full, inner: string) =>
      isMathLike(String(inner)) ? wrapMath(String(inner), format) : full,
    ),
  );

  out = wrapInlineLatexCommands(out);
  // Model often wraps a whole bullet as `$- 1\cdot x = …$`. Stripping those
  // dollars so `- Base = 8 cm` stays prose also used to dump real latex
  // (`\cdot`, `\frac`) onto the list item as raw source. Keep `$…$` when
  // the inner span is math; then re-wrap any leftover bare commands.
  out = out.replace(
    /^(\s*)\$([-*•])\s*(.+?)\s*\$$/,
    (_full, indent: string, mark: string, inner: string) => {
      const body = String(inner).trim();
      if (/\\[a-zA-Z]+/.test(body) || /[\^_]/.test(body) || looksLikeBareEquation(body)) {
        return `${indent}${mark} $${body}$`;
      }
      return `${indent}${mark} ${body}`;
    },
  );
  out = wrapInlineLatexCommands(out);
  return out;
}

export function normalizeImplicitMathInProse(
  text: string,
  format?: (expr: string) => string,
): string {
  return text.split("\n").map((line) => normalizeMathLine(line, format)).join("\n");
}

export function normalizeImplicitMath(
  content: string,
  format?: (expr: string) => string,
): string {
  const chunks: string[] = [];
  let last = 0;
  let match: RegExpExecArray | null;
  while ((match = PROTECTED_SPAN_RE.exec(content)) !== null) {
    if (match.index > last) {
      chunks.push(normalizeImplicitMathInProse(content.slice(last, match.index), format));
    }
    chunks.push(match[0]);
    last = match.index + match[0].length;
  }
  chunks.push(normalizeImplicitMathInProse(content.slice(last), format));
  return chunks.join("");
}
