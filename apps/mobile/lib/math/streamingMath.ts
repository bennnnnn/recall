import { readInlineMathSpan } from "@/lib/markdown/inlineMath";
import {
  PROTECTED_ESCAPE_MARKER,
  PROTECTED_MATH_STAR_MARKER,
  PROTECTED_MATH_UNDERSCORE_MARKER,
} from "@/lib/mathText";

/** In-progress commands/groups are not meaningful native-math previews yet. */
export function hasIncompleteStreamingLatex(body: string): boolean {
  let braces = 0;
  for (let i = 0; i < body.length; i += 1) {
    if (body[i] === "\\") { i += 1; continue; }
    if (body[i] === "{") braces += 1;
    else if (body[i] === "}") braces -= 1;
  }
  const begins = body.match(/\\begin\{[\w*]+\}/g)?.length ?? 0;
  const ends = body.match(/\\end\{[\w*]+\}/g)?.length ?? 0;
  if (braces !== 0 || begins > ends || /\\[A-Za-z]*$/.test(body.trimEnd())) return true;
  // A balanced numerator alone is still only half of a fraction.
  for (const match of body.matchAll(/\\(?:[dtc]?frac)(?![A-Za-z])/g)) {
    let at = match.index + match[0].length;
    for (let arg = 0; arg < 2; arg += 1) {
      while (/\s/.test(body[at] ?? "") && at < body.length) at += 1;
      if (body[at] !== "{") return true;
      let depth = 1;
      at += 1;
      while (at < body.length && depth > 0) {
        if (body[at] === "\\") at += 1;
        else if (body[at] === "{") depth += 1;
        else if (body[at] === "}") depth -= 1;
        at += 1;
      }
      if (depth > 0) return true;
    }
  }
  return false;
}

/** Protect complete inline math in the live tail, holding only an unfinished
 * explicit formula. Ordinary dollars and backticked source remain visible. */
export function prepareStreamingMathText(text: string): { text: string; pending: boolean } {
  let out = "";
  for (let i = 0; i < text.length;) {
    if (text[i - 1] === "(" && text[i] === "$") {
      const tier = /^\${1,4}\)/.exec(text.slice(i));
      if (tier) { out += tier[0]; i += tier[0].length; continue; }
    }
    if (text[i] === "`") {
      let openerEnd = i + 1;
      while (text[openerEnd] === "`") openerEnd += 1;
      const ticks = text.slice(i, openerEnd);
      const end = text.indexOf(ticks, openerEnd);
      const next = end < 0 ? text.length : end + ticks.length;
      out += text.slice(i, next);
      i = next;
      continue;
    }
    const span = readInlineMathSpan(text, i, true);
    if (span) {
      const body = span.value
        // Keep a multiline explicit formula inside one single-dollar span.
        .split(/\r?\n/).map((line) => line.trim()).join(" ")
        .replace(/\\/g, PROTECTED_ESCAPE_MARKER)
        .replace(/_/g, PROTECTED_MATH_UNDERSCORE_MARKER)
        .replace(/\*/g, PROTECTED_MATH_STAR_MARKER);
      out += `$${body}$`;
      i = span.end;
      continue;
    }
    if (text.startsWith("\\(", i) || text.startsWith("\\[", i) || text.startsWith("$$", i)) {
      return { text: out, pending: true };
    }
    if (text[i] === "$" && text.indexOf("$", i + 1) < 0 &&
      /^(?:\\(?:[A-Za-z]|$)|[a-zA-Z](?:[\s_^=]|$)|\d+[_^+*/=-])/.test(text.slice(i + 1))) {
      return { text: out, pending: true };
    }
    if (text[i] === "\\" && i + 1 < text.length) {
      // Preserve escaped dollars/backslashes, rather than treating their
      // second character as a math opener on the next iteration.
      out += text.slice(i, i + 2);
      i += 2;
    } else {
      out += text[i];
      i += 1;
    }
  }
  return { text: out, pending: false };
}
