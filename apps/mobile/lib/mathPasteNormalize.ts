/**
 * Best-effort Unicode math → LaTeX for composer pastes.
 * Glyph set is the client counterpart of `_UNICODE_OP_SUBS` in
 * `apps/api/app/services/math_service/parse.py`.
 */

import { formatMathExpr } from "@/lib/formatMathInput";
import { isMathLike } from "@/lib/normalizeImplicitMath";
import { normalizeUnicodeScripts } from "@/lib/unicodeSupSub";

export const PASTE_GROWTH_MIN = 6;

const VULGAR_FRACTIONS: Record<string, string> = {
  "½": "\\frac{1}{2}",
  "⅓": "\\frac{1}{3}",
  "⅔": "\\frac{2}{3}",
  "¼": "\\frac{1}{4}",
  "¾": "\\frac{3}{4}",
  "⅕": "\\frac{1}{5}",
  "⅖": "\\frac{2}{5}",
  "⅗": "\\frac{3}{5}",
  "⅘": "\\frac{4}{5}",
  "⅙": "\\frac{1}{6}",
  "⅚": "\\frac{5}{6}",
  "⅛": "\\frac{1}{8}",
  "⅜": "\\frac{3}{8}",
  "⅝": "\\frac{5}{8}",
  "⅞": "\\frac{7}{8}",
};

const OP_GLYPHS: [string, string][] = [
  ["×", "\\times "],
  ["÷", "\\div "],
  ["±", "\\pm "],
  ["∓", "\\mp "],
  ["≤", "\\leq "],
  ["≥", "\\geq "],
  ["≠", "\\neq "],
  ["≈", "\\approx "],
  ["∞", "\\infty "],
  ["π", "\\pi "],
  ["·", "\\cdot "],
  ["−", "-"],
];

const MATH_GLYPH_RE = /[½⅓⅔¼¾⅕⅖⅗⅘⅙⅚⅛⅜⅝⅞√×÷±∓≤≥≠≈∞π·−²³¹⁰⁴⁵⁶⁷⁸⁹⁺⁻₀-₉]/;

export function pastedDeltaLooksLikeMath(delta: string): boolean {
  const s = delta.trim();
  if (s.length < 1) return false;
  if (/\*\*|__/.test(s)) return false;
  if (/\$[^$\n]+\$/.test(s) || /```math\b/i.test(s)) return true;
  if (MATH_GLYPH_RE.test(s)) return true;
  if (isMathLike(s) && /[=+\-^√\\]/.test(s)) return true;
  return false;
}

/**
 * Sites like MathPapa copy stacked fractions as HTML. iOS TextInput only
 * gets the accessibility dump: numerator and denominator as separate
 * tokens (`1\\n3 x` or `1 3 x`), so `1/3 x` never reaches slash-to-frac.
 */
export function restoreCopiedFractions(raw: string): string {
  let s = raw.replace(/\u00a0/g, " ");
  s = s.replace(
    /(\d+(?:\.\d+)?)\s*[\n\r]+\s*(\d+(?:\.\d+)?)(?=\s*[a-zA-Z=])/g,
    "\\frac{$1}{$2}",
  );
  if (!/\\frac/.test(s) && !/\d+\s*\/\s*\d/.test(s)) {
    s = s.replace(
      /(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\s*([a-zA-Z])/g,
      "\\frac{$1}{$2} $3",
    );
  }
  return s;
}

function formatPastedExpr(expr: string): string {
  return formatMathExpr(restoreCopiedFractions(expr));
}

export function normalizePastedMath(delta: string): string {
  if (!pastedDeltaLooksLikeMath(delta)) return delta;
  let s = delta;
  for (const [glyph, latex] of Object.entries(VULGAR_FRACTIONS)) {
    s = s.split(glyph).join(latex);
  }
  s = s.replace(/√\s*\(([^()]*)\)/g, "\\sqrt{$1}");
  s = s.replace(/√/g, "\\sqrt{}");
  for (const [glyph, latex] of OP_GLYPHS) {
    s = s.split(glyph).join(latex);
  }
  s = normalizeUnicodeScripts(s);
  const trimmed = s.trim();
  if (!trimmed) return delta;
  if (/```math\b/i.test(trimmed)) {
    return trimmed.replace(/```math\n([\s\S]*?)```/gi, (_m, body: string) => {
      return "```math\n" + formatPastedExpr(String(body).trim()) + "\n```";
    });
  }
  if (trimmed.includes("$")) {
    return s.replace(/\$([^$\n]+)\$/g, (_m, inner: string) => `$${formatPastedExpr(inner)}$`);
  }
  return `$${formatPastedExpr(trimmed)}$`;
}

/** Longest common prefix/suffix → inserted middle. Null if not a paste-sized insert. */
export function extractInsertedDelta(prev: string, next: string): string | null {
  if (next.length <= prev.length) return null;
  let i = 0;
  const minLen = Math.min(prev.length, next.length);
  while (i < minLen && prev[i] === next[i]) i += 1;
  let pe = prev.length;
  let ne = next.length;
  while (pe > i && ne > i && prev[pe - 1] === next[ne - 1]) {
    pe -= 1;
    ne -= 1;
  }
  const inserted = next.slice(i, ne);
  if (inserted.length < 1) return null;
  if (inserted.length < PASTE_GROWTH_MIN && !pastedDeltaLooksLikeMath(inserted)) {
    return null;
  }
  return inserted;
}

export function applyComposerTextChange(prev: string, next: string): string {
  const delta = extractInsertedDelta(prev, next);
  if (delta == null) return next;
  const converted = normalizePastedMath(delta);
  if (converted === delta) return next;
  let i = 0;
  const minLen = Math.min(prev.length, next.length);
  while (i < minLen && prev[i] === next[i]) i += 1;
  let pe = prev.length;
  let ne = next.length;
  while (pe > i && ne > i && prev[pe - 1] === next[ne - 1]) {
    pe -= 1;
    ne -= 1;
  }
  return next.slice(0, i) + converted + next.slice(ne);
}
