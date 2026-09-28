/**
 * Which KaTeX face actually contains a glyph.
 *
 * Checked against katex/dist/fonts (Main, Math-Italic, AMS). Unicode
 * blackboard bold, U+2260 ≠, U+2209 ∉, and U+00B7 · are not in those files.
 * Painting them in a face that lacks the character makes React Native fall
 * back to the UI font. Callers paint a glyph the face does contain.
 */

/** KaTeX `\@not` in KaTeX_Main. Advance matches `=`; ink is the negating slash. */
export const MATH_NOT_GLYPH = "\uE020";
export const NOT_ADVANCE_EM = 0.778;

/** Relations KaTeX builds by overlaying MATH_NOT_GLYPH, plus the base advance. */
export const NEGATED_RELATION: Record<string, { base: string; widthEm: number }> = {
  "≠": { base: "=", widthEm: NOT_ADVANCE_EM },
  "∉": { base: "∈", widthEm: 0.667 },
};

/** In KaTeX_AMS and absent from KaTeX_Main. Everything else in Main stays there. */
export const AMS_ONLY_CHARS = new Set(["∴", "∵"]);

/**
 * Unicode double-struck letters are not in the KaTeX fonts. AMS-Regular draws
 * them at the Latin capitals, which is how KaTeX sets `\mathbb`.
 */
export const BLACKBOARD_LATIN: Record<string, string> = {
  "ℝ": "R",
  "ℤ": "Z",
  "ℕ": "N",
  "ℚ": "Q",
  "ℂ": "C",
  "ℙ": "P",
  "ℍ": "H",
  "𝔽": "F",
  "𝕂": "K",
};

export const BLACKBOARD_ADVANCE_EM = 0.72;
export const CDOT_ADVANCE_EM = 0.28;
export const PRIME_ADVANCE_EM = 0.275;
/** Two Main `|` bars pulled together. U+2016 lives only in the Size1 face. */
export const NORM_ADVANCE_EM = 0.64;

export function primeRun(ch: string): string | null {
  if (ch === "″") return "′′";
  if (ch === "‴") return "′′′";
  return null;
}
