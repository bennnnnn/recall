import { restoreMathEscapes } from "@/lib/mathText";

export type InlineMathPart = { type: "text" | "math"; value: string };

function escapedAt(text: string, at: number): boolean {
  let slashes = 0;
  for (let i = at - 1; i >= 0 && text[i] === "\\"; i -= 1) slashes += 1;
  return slashes % 2 === 1;
}

/** A complete, explicit math span. Currency and escaped dollars stay literal. */
export function readInlineMathSpan(
  text: string,
  start: number,
  display = false,
): { value: string; end: number } | null {
  const opener = text.startsWith("\\(", start) ? "\\("
    : display && text.startsWith("\\[", start) ? "\\["
      : display && text.startsWith("$$", start) ? "$$"
        : text[start] === "$" && text[start - 1] !== "$" && text[start + 1] !== "$" ? "$" : null;
  if (!opener) return null;
  // Check escaping only at an actual opener, not at every character of a
  // backslash run while callers scan the live text one character at a time.
  if (escapedAt(text, start)) return null;
  const closer = opener === "\\(" ? "\\)" : opener === "\\[" ? "\\]" : opener;
  let end = text.indexOf(closer, start + opener.length);
  while (end >= 0 && escapedAt(text, end)) end = text.indexOf(closer, end + closer.length);
  if (end < 0) return null;
  const value = text.slice(start + opener.length, end);
  if (!value.trim() || (opener === "$" && value.includes("\n"))) return null;
  // "$5 and $10" contains two prices, not a math span ending before "10".
  if (opener === "$" && /^\d/.test(text.slice(end + 1))) return null;
  // Do not pair a price with a later formula's opener: "$10; $x=2$".
  if (opener === "$") {
    const price = /^\d[\d,.]*(?:[;:!?](?:\s.*)?|\s+([A-Za-z]+).*)$/.exec(value);
    const word = price?.[1] ?? "";
    const mathWord = /^[a-z]$|^(?:sin|cos|tan|sec|csc|cot|log|ln|exp|lim|max|min)$/i.test(word);
    if (price && !mathWord) return null;
  }
  return { value: value.trim(), end: end + closer.length };
}

function looksLikeEnglishMathSpan(inner: string): boolean {
  if (/\\[a-zA-Z]+/.test(restoreMathEscapes(inner))) return false;
  return (inner.match(/[A-Za-z]{3,}/g) ?? []).length >= 2;
}

/** Split prose without interpreting inline code or currency as mathematics. */
export function splitInlineMath(text: string): InlineMathPart[] {
  const parts: InlineMathPart[] = [];
  let last = 0;
  for (let i = 0; i < text.length;) {
    if (text[i] === "`") {
      let fenceEnd = i + 1;
      while (text[fenceEnd] === "`") fenceEnd += 1;
      const close = text.indexOf(text.slice(i, fenceEnd), fenceEnd);
      const markerLength = fenceEnd - i;
      i = close < 0 ? text.length : close + markerLength;
      continue;
    }
    const span = readInlineMathSpan(text, i);
    if (!span) { i += 1; continue; }
    if (i > last) parts.push({ type: "text", value: text.slice(last, i) });
    parts.push({ type: looksLikeEnglishMathSpan(span.value) ? "text" : "math", value: span.value });
    i = span.end;
    last = i;
  }
  if (last < text.length) parts.push({ type: "text", value: text.slice(last) });
  return parts.length ? parts : [{ type: "text", value: text }];
}
