/** First line of a server answer fence. Absent means the body is LaTeX. */

export const CHEMISTRY_ANSWER_NOTATION = "notation: chemistry";

const SUPERSCRIPT_DIGITS: Record<string, string> = {
  "-": "⁻",
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
};

function superscript(exponent: string): string {
  return [...exponent].map((char) => SUPERSCRIPT_DIGITS[char] ?? char).join("");
}

/**
 * A typeset answer card as plain text. The web has no math renderer, and the server writes
 * physics cards as LaTeX with upright units: `3.97 \times 10^{-19}\,\mathrm{J}` reads
 * `3.97 × 10⁻¹⁹ J`, exactly the server's own plain answer. Anything else stays as written.
 */
export function readableLatexAnswer(latex: string): string {
  return latex
    .replace(/\\(?:mathrm|text)\{([^{}]*)\}/g, "$1")
    .replace(/_\{([^{}]*)\}/g, "_$1")
    .replace(/\\times 10\^\{(-?\d+)\}/g, (_match, exponent: string) => `× 10${superscript(exponent)}`)
    .replace(/\^\\circ/g, "°")
    .replace(/\\Omega(?![A-Za-z])/g, "Ω")
    .replace(/\\%/g, "%")
    .replace(/;\\quad /g, "; ")
    .replace(/\\quad(?![A-Za-z])/g, " ")
    .replace(/\\[,;:! ]/g, " ")
    .replace(/ {2,}/g, " ")
    .trim();
}

export function visibleAnswerBody(raw: string): string {
  const text = raw.replace(/\r\n/g, "\n").trim();
  const newline = text.indexOf("\n");
  if (newline > 0 && text.slice(0, newline).trim() === CHEMISTRY_ANSWER_NOTATION) {
    return text.slice(newline + 1).trim();
  }
  return text.includes("\\") ? readableLatexAnswer(text) : text;
}
