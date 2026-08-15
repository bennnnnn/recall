/**
 * Best-effort Unicode math → LaTeX for composer pastes.
 * Glyph set is the client counterpart of `_UNICODE_OP_SUBS` in
 * `apps/api/app/services/math_service/parse.py`.
 */

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
  if (MATH_GLYPH_RE.test(s)) return true;
  if (isMathLike(s) && /[=+\-^√\\]/.test(s)) return true;
  return false;
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
  if (trimmed.includes("$")) return s;
  return `$${trimmed}$`;
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
  if (inserted.length < PASTE_GROWTH_MIN) return null;
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
