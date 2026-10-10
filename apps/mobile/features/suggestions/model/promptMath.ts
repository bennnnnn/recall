/**
 * Turn a follow-up question into text MathText can typeset.
 * The model is asked for `$x^2 = 9$`. A bare `X^2 = 9` still gets dollars
 * so the caret is a superscript, matching the answer above the line.
 * Already-delimited spans are left alone.
 */

const MATH_ISLAND =
  /[A-Za-z](?:\s*[\^_]\s*(?:\{[^{}\n]+\}|\d+))+(?:\s*[-+*/=]\s*(?:[A-Za-z]|\d+(?:\.\d+)?))*/g;

export function wrapSuggestionMath(text: string): string {
  let out = "";
  let i = 0;
  while (i < text.length) {
    if (text[i] === "$") {
      const close = text.indexOf("$", i + 1);
      if (close > i + 1) {
        out += text.slice(i, close + 1);
        i = close + 1;
        continue;
      }
    }
    MATH_ISLAND.lastIndex = i;
    const match = MATH_ISLAND.exec(text);
    if (!match) {
      out += text.slice(i);
      break;
    }
    const dollar = text.indexOf("$", i);
    if (dollar !== -1 && dollar < match.index) {
      out += text.slice(i, dollar);
      i = dollar;
      continue;
    }
    out += text.slice(i, match.index);
    out += `$${match[0]}$`;
    i = match.index + match[0].length;
  }
  return out;
}
