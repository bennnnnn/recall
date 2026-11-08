import { readInlineMathSpan } from "@/lib/markdown/inlineMath";
import { formulaText } from "@/lib/math/text";

/**
 * A message hit's line as the drawer shows it. The server sends the words without their
 * markdown, each formula kept whole between `$` marks and a dollar it knows is not maths
 * (code's `$HOME`) escaped as `\$` (`modules/search/snippet.py`). Only `$` opens a formula
 * here: the server writes every formula that way, so a `\(` left in a hit is code's own.
 * A formula reads as one line of symbols, never its TeX: `$v_0 = 20\,\mathrm{m/s}$` is
 * "v_0 = 20 m/s". The highlight is cut from this line, so it lands on the words shown.
 */
export function snippetText(content: string): string {
  let out = "";
  let last = 0;
  for (let at = content.indexOf("$"); at !== -1; at = content.indexOf("$", at + 1)) {
    // A formula right after another ($a$$b$) opens where the last one closed.
    const span = at === last && at > 0 ? offsetSpan(content, at) : readInlineMathSpan(content, at);
    if (!span) continue;
    out += unescaped(content.slice(last, at)) + formulaText(span.value);
    last = span.end;
    at = span.end - 1;
  }
  return out + unescaped(content.slice(last));
}

function offsetSpan(content: string, at: number): { value: string; end: number } | null {
  const span = readInlineMathSpan(content.slice(at), 0);
  return span ? { value: span.value, end: at + span.end } : null;
}

function unescaped(text: string): string {
  return text.replaceAll("\\$", "$");
}
