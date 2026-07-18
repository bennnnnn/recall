import { toSubscript, toSuperscript } from "@/lib/unicodeSupSub";

/**
 * Unicode FRACTION SLASH (U+2044). Unlike solidus "/" or box-drawing "─",
 * this is the character fonts use to compose diagonal vulgar-style fractions
 * from superscript + slash + subscript (e.g. ¹¹⁄₁₂).
 * @see https://unicodefyi.com/guide/fraction-symbols-guide/
 */
export const FRACTION_SLASH = "\u2044";

/** Precomposed vulgar fractions — single glyphs that actually look like fractions. */
const VULGAR_FRACTIONS: Record<string, string> = {
  "1/2": "½",
  "1/3": "⅓",
  "2/3": "⅔",
  "1/4": "¼",
  "3/4": "¾",
  "1/5": "⅕",
  "2/5": "⅖",
  "3/5": "⅗",
  "4/5": "⅘",
  "1/6": "⅙",
  "5/6": "⅚",
  "1/7": "⅐",
  "1/8": "⅛",
  "3/8": "⅜",
  "5/8": "⅝",
  "7/8": "⅞",
  "1/9": "⅑",
  "1/10": "⅒",
  "0/3": "↉",
};

/**
 * Best Unicode glyph for a simple fraction, or null when the caller should
 * fall back to plain solidus layout (letters, nested math, etc.).
 *
 * Order: precomposed vulgar (½) → digit superscript + ⁄ + subscript (¹¹⁄₁₂).
 * Never use a horizontal bar between raised/lowered chars — that reads as
 * "¹ — ₂", not a fraction.
 */
export function unicodeFractionGlyph(num: string, den: string): string | null {
  const key = `${num}/${den}`;
  const vulgar = VULGAR_FRACTIONS[key];
  if (vulgar) return vulgar;

  if (!/^[0-9]+$/.test(num) || !/^[0-9]+$/.test(den)) return null;
  const numUni = toSuperscript(num);
  const denUni = toSubscript(den);
  if (!numUni || !denUni) return null;
  return `${numUni}${FRACTION_SLASH}${denUni}`;
}
