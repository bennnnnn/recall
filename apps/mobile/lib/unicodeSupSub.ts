/**
 * Unicode superscript / subscript characters for the Expo-Go math fallback.
 *
 * `MathText` renders math as native Text (no KaTeX WebView in Expo Go). Its
 * `sup`/`sub` styles are just smaller text at the baseline — they don't raise
 * the exponent, so `2^x` reads as `2_x` (subscript) instead of `2ˣ`. Mapping
 * exponents to real Unicode superscripts makes them render raised in plain
 * text with no WebView. When a character has no Unicode super/subscript (e.g.
 * a parenthesis or an unusual letter), the caller falls back to the styled
 * smaller-Text rendering.
 */

const SUPERSCRIPT: Record<string, string> = {
  "0": "⁰",
  "1": "¹",
  "2": "²",
  "3": "³",
  "4": "⁴",
  "5": "⁵",
  "6": "⁶",
  "7": "⁷",
  "8": "⁸",
  "9": "⁹",
  "+": "⁺",
  "-": "⁻",
  "=": "⁼",
  "(": "⁽",
  ")": "⁾",
  a: "ᵃ",
  b: "ᵇ",
  c: "ᶜ",
  d: "ᵈ",
  e: "ᵉ",
  f: "ᶠ",
  g: "ᵍ",
  h: "ʰ",
  i: "ⁱ",
  j: "ʲ",
  k: "ᵏ",
  l: "ˡ",
  m: "ᵐ",
  n: "ⁿ",
  o: "ᵒ",
  p: "ᵖ",
  r: "ʳ",
  s: "ˢ",
  t: "ᵗ",
  u: "ᵘ",
  v: "ᵛ",
  w: "ʷ",
  x: "ˣ",
  y: "ʸ",
  z: "ᶻ",
  A: "ᴬ",
  B: "ᴮ",
  D: "ᴰ",
  E: "ᴱ",
  G: "ᴳ",
  H: "ᴴ",
  I: "ᴵ",
  J: "ᴶ",
  K: "ᴷ",
  L: "ᴸ",
  M: "ᴹ",
  N: "ᴺ",
  O: "ᴼ",
  P: "ᴾ",
  R: "ᴿ",
  T: "ᵀ",
  U: "ᵁ",
  V: "ⱽ",
  W: "ᵂ",
};

const SUBSCRIPT: Record<string, string> = {
  "0": "₀",
  "1": "₁",
  "2": "₂",
  "3": "₃",
  "4": "₄",
  "5": "₅",
  "6": "₆",
  "7": "₇",
  "8": "₈",
  "9": "₉",
  "+": "₊",
  "-": "₋",
  "=": "₌",
  "(": "₍",
  ")": "₎",
  a: "ₐ",
  e: "ₑ",
  h: "ₕ",
  i: "ᵢ",
  j: "ⱼ",
  k: "ₖ",
  l: "ₗ",
  m: "ₘ",
  n: "ₙ",
  o: "ₒ",
  p: "ₚ",
  r: "ᵣ",
  s: "ₛ",
  t: "ₜ",
  u: "ᵤ",
  v: "ᵥ",
  x: "ₓ",
};

function toVerticalForm(value: string, map: Record<string, string>): string | null {
  if (!value) return null;
  let out = "";
  for (const ch of value) {
    const mapped = map[ch];
    if (!mapped) return null; // any unmapped char → caller falls back to styled Text
    out += mapped;
  }
  return out;
}

/** Return the Unicode superscript for `value` (e.g. "x" → "ˣ", "2" → "²"),
 * or null if any character lacks a Unicode superscript. */
export function toSuperscript(value: string): string | null {
  return toVerticalForm(value, SUPERSCRIPT);
}

/** Return the Unicode subscript for `value`, or null if any character lacks
 * a Unicode subscript. */
export function toSubscript(value: string): string | null {
  return toVerticalForm(value, SUBSCRIPT);
}
