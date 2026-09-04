/**
 * Math input formatter — a single place that holds the features for cleaning up
 * math a user typed in the composer so it renders nicely.
 *
 * The power feature (`x2` → `x^2`) is keypad-only OCR
 * (`applyImplicitPowerNotation`). Model replies do not rewrite digits.
 * Also: spacing around `=` / binary `+` / binary `-`, relational glyphs,
 * `+-` → `\pm`, `*` → `\times`, simple `a/b` → `\frac{a}{b}`.
 *
 * Paste and history can still call `formatMathExpr`. Send stays verbatim
 * (`messageTextForSend`) so the user bubble matches the composer.
 */

import { applyImplicitPowerNotation, isMathLike } from "@/lib/normalizeImplicitMath";

export type MathFormatOptions = {
  /** `x2` → `x^2` (OCR's dropped caret). Default true. */
  power?: boolean;
  /** `x=3` → `x = 3`, `a-b` → `a - b` (binary only). Default true. */
  spacing?: boolean;
  /** `>=` → `\geq`, `<=` → `\leq`, `!=` → `\neq`. Default true. */
  relations?: boolean;
  /** `+-` → `\pm`. Default true. */
  pm?: boolean;
  /** Binary `*` → `\times` (not markdown `**`). Default true. */
  times?: boolean;
  /** Simple `a/b` → `\frac{a}{b}`. Default true. */
  slashFrac?: boolean;
};

const DEFAULTS: Required<MathFormatOptions> = {
  power: true,
  spacing: true,
  relations: true,
  pm: true,
  times: true,
  slashFrac: true,
};

/** Characters that count as the right-hand operand of a binary operator. */
const OPERAND_TAIL = /[a-zA-Z0-9.)\]}]/;
const ATOM = /^(?:\d+(?:\.\d+)?|[a-zA-Z])/;

function lastNonSpace(s: string): string {
  let k = s.length - 1;
  while (k >= 0 && /\s/.test(s[k]!)) k -= 1;
  return s[k] ?? "";
}

function skipLatexCommand(s: string, i: number): number {
  let j = i + 1;
  if (j < s.length && /[a-zA-Z]/.test(s[j]!)) {
    while (j < s.length && /[a-zA-Z]/.test(s[j]!)) j += 1;
  } else {
    j = i + 2;
  }
  return j;
}

/** Skip `\cmd`, optional `[...]` (nth-root index), then `{...}` groups. */
function skipLatexArgs(s: string, i: number): number {
  let j = skipLatexCommand(s, i);
  if (s[j] === "[") {
    const close = s.indexOf("]", j);
    if (close !== -1) j = close + 1;
  }
  while (s[j] === "{") {
    const next = skipBraceGroup(s, j);
    if (next === j) break;
    j = next;
  }
  return j;
}

function skipBraceGroup(s: string, i: number): number {
  let depth = 0;
  let j = i;
  while (j < s.length) {
    if (s[j] === "{") depth += 1;
    else if (s[j] === "}") {
      depth -= 1;
      if (depth === 0) return j + 1;
    }
    j += 1;
  }
  return j;
}

function readAtom(s: string, i: number): { atom: string; next: number } | null {
  let j = i;
  while (j < s.length && /\s/.test(s[j]!)) j += 1;
  const slice = s.slice(j);
  const m = slice.match(ATOM);
  if (!m) return null;
  return { atom: m[0], next: j + m[0].length };
}

function lastAtomStart(s: string): { atom: string; start: number } | null {
  const t = s.replace(/\s+$/, "");
  const m = t.match(/(?:\d+(?:\.\d+)?|[a-zA-Z])$/);
  if (!m || m.index == null) return null;
  return { atom: m[0], start: m.index };
}

/** Binary `*` → `\times`. Leaves `**` markdown alone. */
function timesOperators(s: string): string {
  let out = "";
  let i = 0;
  const n = s.length;
  while (i < n) {
    if (s[i] === "\\") {
      const j = skipLatexArgs(s, i);
      out += s.slice(i, j);
      i = j;
      continue;
    }
    if (s.startsWith("**", i)) {
      out += "**";
      i += 2;
      continue;
    }
    if (s[i] === "*") {
      const prev = lastNonSpace(out);
      let k = i + 1;
      while (k < n && /\s/.test(s[k]!)) k += 1;
      const nextCh = s[k] ?? "";
      const binary = OPERAND_TAIL.test(prev) && /[a-zA-Z0-9.(\\[]/.test(nextCh);
      if (binary) {
        out = out.replace(/\s+$/, "") + " \\times ";
        i += 1;
        continue;
      }
    }
    out += s[i];
    i += 1;
  }
  return out;
}

/** Length/time unit slashes (`m/s`, `km/h`) — not algebraic `a/b`. */
function isUnitSlash(left: string, right: string): boolean {
  return /^(?:nm|mm|cm|km|m)$/i.test(left) && /^(?:ms|min|hr|s|h)$/i.test(right);
}

/** Simple `a/b` (number or single letter) → `\frac{a}{b}`. */
function slashToFrac(s: string): string {
  let out = "";
  let i = 0;
  const n = s.length;
  while (i < n) {
    if (s[i] === "\\") {
      const j = skipLatexArgs(s, i);
      out += s.slice(i, j);
      i = j;
      continue;
    }
    if ((s[i] === "^" || s[i] === "_") && s[i + 1] === "{") {
      const j = skipBraceGroup(s, i + 1);
      out += s.slice(i, j);
      i = j;
      continue;
    }
    if (s[i] === "/") {
      const left = lastAtomStart(out);
      const right = readAtom(s, i + 1);
      if (left && right && !isUnitSlash(left.atom, right.atom)) {
        out = out.slice(0, left.start) + `\\frac{${left.atom}}{${right.atom}}`;
        i = right.next;
        continue;
      }
    }
    out += s[i];
    i += 1;
  }
  return out;
}

/**
 * `9\sqrt{9}` is 9 × square-root, not the 9th root `\sqrt[9]{9}`.
 * Leave `\sqrt[...]{...}` (ⁿ√) alone.
 */
function implicitTimesBeforeSqrt(s: string): string {
  let out = "";
  let i = 0;
  const n = s.length;
  while (i < n) {
    if (s.startsWith("\\sqrt", i) && s[i + 5] !== "[") {
      const trimmed = out.replace(/\s+$/, "");
      const prev = lastNonSpace(trimmed);
      const afterBareCommand = /\\[a-zA-Z]+$/.test(trimmed);
      if (OPERAND_TAIL.test(prev) && !afterBareCommand) {
        out = trimmed + " \\times ";
      }
    }
    if (s[i] === "\\") {
      const j = skipLatexArgs(s, i);
      out += s.slice(i, j);
      i = j;
      continue;
    }
    out += s[i];
    i += 1;
  }
  return out;
}

/**
 * Space `=` and binary `+`/`-`. Leaves `^{...}` / `_{...}` groups (exponents
 * and indices) and `\command` names verbatim so grouping and LaTeX commands
 * are never corrupted. Unary `+`/`-` (start, or after an operator / `(` /
 * `=` / `,`) is left unspaced.
 */
function spaceOperators(s: string): string {
  let out = "";
  let i = 0;
  const n = s.length;
  while (i < n) {
    const ch = s[i]!;
    if (ch === "\\") {
      const j = skipLatexArgs(s, i);
      out += s.slice(i, j);
      i = j;
      continue;
    }
    if ((ch === "^" || ch === "_") && s[i + 1] === "{") {
      const j = skipBraceGroup(s, i + 1);
      out += s.slice(i, j);
      i = j;
      continue;
    }
    if (ch === "^" || ch === "_") {
      out += ch + (s[i + 1] ?? "");
      i += 2;
      continue;
    }
    if (ch === "=") {
      out = out.replace(/\s+$/, "") + " = ";
      i += 1;
      continue;
    }
    if (ch === "+" || ch === "-") {
      const prev = lastNonSpace(out);
      const binary = OPERAND_TAIL.test(prev) && prev !== "=";
      if (binary) {
        out = out.replace(/\s+$/, "") + ` ${ch} `;
      } else {
        out += ch;
      }
      i += 1;
      continue;
    }
    out += ch;
    i += 1;
  }
  return out.replace(/\s+/g, " ").trim();
}

function formatDollarSpans(text: string): string {
  return text.replace(/\$([^$\n]+)\$/g, (_m, inner: string) => `$${formatMathExpr(inner)}$`);
}

function formatMathFences(text: string): string {
  return text.replace(/```math\n([\s\S]*?)```/gi, (_m, body: string) => {
    return "```math\n" + formatMathExpr(String(body).trim()) + "\n```";
  });
}

/** Format a single math expression (no prose). */
export function formatMathExpr(
  expr: string,
  opts: MathFormatOptions = {},
): string {
  const o = { ...DEFAULTS, ...opts };
  let s = expr.trim();
  if (!s) return s;
  if (o.power) s = applyImplicitPowerNotation(s);
  if (o.relations) {
    s = s.replace(/<=/g, " \\leq ").replace(/>=/g, " \\geq ").replace(/!=/g, " \\neq ");
  }
  if (o.pm) {
    // Only glued `+-` (OCR / typed ±). Spaced `+ -5` is plus then unary
    // minus — MathPapa writes that, and `\+\s*-` used to smash it into `\pm`.
    s = s.replace(/\+-/g, " \\pm ");
  }
  if (o.times) s = timesOperators(s);
  if (o.slashFrac) s = slashToFrac(s);
  s = implicitTimesBeforeSqrt(s);
  if (o.spacing) {
    s = spaceOperators(s);
  }
  return s.replace(/\s+/g, " ").trim();
}

/**
 * Format math in a whole composer/send payload: `$...$` and ```math bodies,
 * or wrap a bare math-like message in `$...$`.
 */
export function formatMathMessage(text: string): string {
  const trimmed = text.trim();
  if (!trimmed) return trimmed;
  let out = formatMathFences(trimmed);
  out = formatDollarSpans(out);
  if (!out.includes("$") && !/```math/i.test(out) && isMathLike(out)) {
    return `$${formatMathExpr(out)}$`;
  }
  return out;
}
