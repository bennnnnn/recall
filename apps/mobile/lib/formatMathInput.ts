/**
 * Math input formatter — a single place that holds the features for cleaning up
 * math a user typed in the composer so it renders nicely.
 *
 * The power feature (`x2` → `x^2`) reuses `fixImplicitExponents` from
 * normalizeImplicitMath (the "power of (x^y)" formatter we already had).
 * The rest is new: spacing around `=` / binary `+` / binary `-`, relational
 * glyph normalization (`>=` → `\geq`, `<=` → `\leq`, `!=` → `\neq`), and
 * `+-` → `\pm`. Each feature is toggleable so callers can compose only
 * what they need.
 *
 * Pure display formatter — does NOT change what is sent to the backend
 * (the backend math-intent extractor sees the user's original text), only
 * how the user's message renders in their own bubble.
 */

import { fixImplicitExponents } from "@/lib/normalizeImplicitMath";

export type MathFormatOptions = {
  /** `x2` → `x^2` (OCR's dropped caret). Default true. */
  power?: boolean;
  /** `x=3` → `x = 3`, `a-b` → `a - b` (binary only). Default true. */
  spacing?: boolean;
  /** `>=` → `\geq`, `<=` → `\leq`, `!=` → `\neq`. Default true. */
  relations?: boolean;
  /** `+-` → `\pm`. Default true. */
  pm?: boolean;
};

const DEFAULTS: Required<MathFormatOptions> = {
  power: true,
  spacing: true,
  relations: true,
  pm: true,
};

/** Characters that count as the right-hand operand of a binary operator. */
const OPERAND_TAIL = /[a-zA-Z0-9.)\]}]/;

function lastNonSpace(s: string): string {
  let k = s.length - 1;
  while (k >= 0 && /\s/.test(s[k]!)) k -= 1;
  return s[k] ?? "";
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
    // LaTeX command: backslash + letters (or one non-letter) — copy verbatim.
    if (ch === "\\") {
      let j = i + 1;
      if (j < n && /[a-zA-Z]/.test(s[j]!)) {
        while (j < n && /[a-zA-Z]/.test(s[j]!)) j += 1;
      } else {
        j = i + 2;
      }
      out += s.slice(i, j);
      i = j;
      continue;
    }
    // ^{...} / _{...} group — copy the balanced group verbatim (no spacing
    // inside an exponent/index; `x^{n+1}` must not become `x^{n + 1}`).
    if ((ch === "^" || ch === "_") && s[i + 1] === "{") {
      let depth = 0;
      let j = i + 1;
      while (j < n) {
        if (s[j] === "{") depth += 1;
        else if (s[j] === "}") {
          depth -= 1;
          if (depth === 0) {
            j += 1;
            break;
          }
        }
        j += 1;
      }
      out += s.slice(i, j);
      i = j;
      continue;
    }
    // Bare ^x / _x (no braces) — copy the marker + its single char verbatim.
    if (ch === "^" || ch === "_") {
      out += ch + (s[i + 1] ?? "");
      i += 2;
      continue;
    }
    // Standalone `=` → " = ". Relations (<=, >=, !=) are already converted
    // to \leq/\geq/\neq before this runs, so `=` here is only equality.
    if (ch === "=") {
      out = out.replace(/\s+$/, "") + " = ";
      i += 1;
      continue;
    }
    // Binary + / - get spaces; unary (after operator/`(`/`=`/`,`/start) stays.
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

/** Format a single math expression (no prose). */
export function formatMathExpr(
  expr: string,
  opts: MathFormatOptions = {},
): string {
  const o = { ...DEFAULTS, ...opts };
  let s = expr.trim();
  if (!s) return s;
  if (o.power) s = fixImplicitExponents(s);
  // Relations first so `=` only appears as standalone equality below.
  if (o.relations) {
    s = s.replace(/<=/g, " \\leq ").replace(/>=/g, " \\geq ").replace(/!=/g, " \\neq ");
  }
  if (o.pm) {
    s = s.replace(/\+\s*-/g, " \\pm ");
  }
  if (o.spacing) {
    s = spaceOperators(s);
  }
  return s.replace(/\s+/g, " ").trim();
}
