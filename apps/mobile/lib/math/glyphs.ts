/**
 * Which KaTeX face actually contains a glyph, and the em advance it draws at.
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

const BLACKBOARD_ADVANCE_EM = 0.72;
const CDOT_ADVANCE_EM = 0.28;
const PRIME_ADVANCE_EM = 0.275;
/** Two Main `|` bars pulled together. U+2016 lives only in the Size1 face. */
export const NORM_ADVANCE_EM = 0.64;

export function primeRun(ch: string): string | null {
  if (ch === "″") return "′′";
  if (ch === "‴") return "′′′";
  return null;
}

/**
 * Arrow advances in KaTeX_Main (katex fontMetricsData). A sideways arrow is a
 * full em and a long one over 1.6; measured as an unknown glyph (0.7 em), a
 * formula with `\rightarrow` came out narrower than its ink.
 */
const ARROW_ADVANCE_EM: Record<string, number> = {
  "↑": 0.5, "↓": 0.5, "↕": 0.5, "⇑": 0.611, "⇓": 0.611, "⇕": 0.611,
  "↩": 1.126, "↪": 1.126,
  "⟵": 1.609, "⟸": 1.609, "⟶": 1.638, "⟹": 1.638, "⟼": 1.638, "⟷": 1.859, "⟺": 1.858,
};

/** The em advance of an arrow glyph, or null when `ch` is not an arrow. */
function arrowAdvanceEm(ch: string): number | null {
  const listed = ARROW_ADVANCE_EM[ch];
  if (listed != null) return listed;
  const code = ch.codePointAt(0) ?? 0;
  return code >= 0x2190 && code <= 0x21ff ? 1 : null;
}

/**
 * TeX's italic correction in KaTeX_MathItalic (katex fontMetricsData), in em: how far a
 * letter's ink leans past its advance. A box that ends on the letter cuts that much of it
 * off: `P` drew as `F`, and V and Y lean furthest. A letter not listed leans none.
 */
const ITALIC_CORRECTION_EM: Record<string, number> = {
  B: 0.05, C: 0.072, D: 0.028, E: 0.058, F: 0.139, H: 0.081, I: 0.078, J: 0.096, K: 0.072,
  M: 0.109, N: 0.109, O: 0.028, P: 0.139, R: 0.008, S: 0.058, T: 0.139, U: 0.109, V: 0.222,
  W: 0.139, X: 0.078, Y: 0.222, Z: 0.072, f: 0.108, g: 0.036, j: 0.057, k: 0.031, l: 0.02,
  q: 0.036, r: 0.028, v: 0.036, w: 0.027, y: 0.036, z: 0.044,
  "Γ": 0.139, "Θ": 0.028, "Ξ": 0.076, "Π": 0.081, "Σ": 0.058, "Υ": 0.139, "Ψ": 0.11, "Ω": 0.05,
  "α": 0.004, "β": 0.053, "γ": 0.056, "δ": 0.038, "ζ": 0.074, "η": 0.036, "θ": 0.028,
  "ν": 0.064, "ξ": 0.046, "π": 0.036, "ς": 0.08, "σ": 0.036, "τ": 0.113, "υ": 0.036,
  "ψ": 0.036, "ω": 0.036, "ϖ": 0.028,
};

/** How far an italic letter's ink leans past its advance, in em (0 for any other glyph). */
export function italicCorrectionEm(ch: string): number {
  return ITALIC_CORRECTION_EM[ch] ?? 0;
}

const WIDE = new Set(["m", "w", "M", "W"]);
const NARROW = new Set(["i", "l", "I", "j", "f", "t", "r"]);

function isCombiningMark(ch: string): boolean {
  const c = ch.charCodeAt(0);
  return c >= 0x0300 && c <= 0x036f;
}

/** Em advance for one glyph. Unknown characters still take positive space. */
export function glyphAdvanceEm(ch: string): number {
  if (isCombiningMark(ch)) return 0;
  if (ch === " " || ch === "\u00a0" || ch === "\u2009") return 0.33;
  if (ch >= "0" && ch <= "9") return 0.5;
  if (ch === "m" || ch === "M") return 0.9;
  if (ch === "w" || ch === "W") return 0.85;
  if (WIDE.has(ch)) return 0.8;
  if (NARROW.has(ch)) return 0.32;
  if (/[A-Za-z]/.test(ch)) {
    return ch.toLowerCase() !== ch ? 0.72 : 0.52;
  }
  if (ch === "·" || ch === "⋅") return CDOT_ADVANCE_EM;
  if (ch === "″") return PRIME_ADVANCE_EM * 2;
  if (ch === "‴") return PRIME_ADVANCE_EM * 3;
  if (ch === "‖") return NORM_ADVANCE_EM;
  if (NEGATED_RELATION[ch]) return NEGATED_RELATION[ch].widthEm;
  if (BLACKBOARD_LATIN[ch]) return BLACKBOARD_ADVANCE_EM;
  if (".,:;'`′″‴".includes(ch)) return 0.28;
  if ("()[]{}|/".includes(ch)) return 0.4;
  if ("+-−=<>±∓×÷".includes(ch)) return 0.78;
  const arrow = arrowAdvanceEm(ch);
  if (arrow != null) return arrow;
  const code = ch.codePointAt(0) ?? 0;
  if (code >= 0x370 && code <= 0x3ff) return 0.62;
  if (code > 0x7f) return 0.7;
  return 0.5;
}
