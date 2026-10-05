/**
 * Put a visible word space outside closed inline Markdown tokens.
 * Mirrors apps/api/app/services/chat/inline_boundaries.py.
 * Fenced code, indented code, blockquotes, URLs, and math bodies stay intact.
 */

import { applyOutsideFences } from "@/lib/mdFenceScan";

const OPEN_PUNCT = new Set("([{\"“‘«".split(""));
const CLOSE_PUNCT = new Set(".,;:!?)]}\"”’»…—–/%".split(""));

function isCjk(char: string): boolean {
  const code = char.charCodeAt(0);
  return (
    (code >= 0x3040 && code <= 0x30ff) ||
    (code >= 0x3400 && code <= 0x9fff) ||
    (code >= 0xac00 && code <= 0xd7af) ||
    (code >= 0x0e00 && code <= 0x0e7f) ||
    (code >= 0xf900 && code <= 0xfaff)
  );
}

function needsWordSpace(char: string): boolean {
  if (!char || /\s/.test(char) || isCjk(char)) return false;
  return char.toLowerCase() !== char.toUpperCase() || /\d/.test(char);
}

function glueBefore(previous: string): boolean {
  if (!previous || /\s/.test(previous) || OPEN_PUNCT.has(previous)) return false;
  return needsWordSpace(previous);
}

function glueAfter(next: string): boolean {
  if (!next || /\s/.test(next) || CLOSE_PUNCT.has(next)) return false;
  // A following delimiter is another inline token, not punctuation.
  if ("$*`[".includes(next)) return true;
  return needsWordSpace(next);
}

function skipCommand(text: string, index: number): number {
  let cursor = index + 1;
  if (cursor < text.length && /[A-Za-z]/.test(text[cursor])) {
    while (cursor < text.length && /[A-Za-z]/.test(text[cursor])) cursor += 1;
  } else if (cursor < text.length) {
    cursor += 1;
  }
  return cursor;
}

function readUrl(text: string, index: number): number | null {
  if (
    !text.startsWith("https://", index) &&
    !text.startsWith("http://", index) &&
    !text.startsWith("www.", index)
  ) {
    return null;
  }
  let cursor = index;
  while (cursor < text.length && !/\s/.test(text[cursor])) cursor += 1;
  return cursor;
}

function readCode(text: string, index: number): number | null {
  if (text[index] !== "`") return null;
  let length = 0;
  while (index + length < text.length && text[index + length] === "`") length += 1;
  const close = text.indexOf("`".repeat(length), index + length);
  if (close < 0 || close === index + length || text.slice(index + length, close).includes("\n")) {
    return null;
  }
  return close + length;
}

function escapedDollar(text: string, index: number): boolean {
  let slashes = 0;
  for (let i = index - 1; i >= 0 && text[i] === "\\"; i -= 1) slashes += 1;
  return slashes % 2 === 1;
}

function readMath(text: string, index: number): number | null {
  if (escapedDollar(text, index)) return null;
  if (text.startsWith("$$", index)) {
    const close = text.indexOf("$$", index + 2);
    if (close < 0 || close === index + 2 || text.slice(index + 2, close).includes("\n")) return null;
    return close + 2;
  }
  if (text[index] !== "$" || (index > 0 && text[index - 1] === "$")) return null;
  let from = index + 1;
  while (from < text.length) {
    const close = text.indexOf("$", from);
    if (close < 0 || text.slice(index + 1, close).includes("\n")) return null;
    if (escapedDollar(text, close)) {
      from = close + 1;
      continue;
    }
    if (close + 1 < text.length && text[close + 1] === "$") return null;
    const body = text.slice(index + 1, close);
    if (!body.trim()) return null;
    if (/^\d/.test(body) && !/[\\=^_]/.test(body)) return null;
    return close + 1;
  }
  return null;
}

function readLink(text: string, index: number): number | null {
  let cursor = index;
  if (text[cursor] === "!" && text[cursor + 1] === "[") cursor += 1;
  if (text[cursor] !== "[") return null;
  const close = text.indexOf("]", cursor + 1);
  if (close < 0 || text.slice(cursor + 1, close).includes("\n")) return null;
  if (text[close + 1] === "(") {
    const end = text.indexOf(")", close + 2);
    if (end < 0 || text.slice(close + 2, end).includes("\n")) return null;
    return end + 1;
  }
  if (text[close + 1] === "[") {
    const end = text.indexOf("]", close + 2);
    if (end < 0 || text.slice(close + 2, end).includes("\n")) return null;
    return end + 1;
  }
  return null;
}

function readBold(text: string, index: number): number | null {
  if (!text.startsWith("**", index)) return null;
  const markerLen = text.startsWith("***", index) ? 3 : 2;
  const close = text.indexOf("*".repeat(markerLen), index + markerLen);
  if (close < 0) return null;
  const inner = text.slice(index + markerLen, close);
  if (!inner.trim() || inner.includes("\n")) return null;
  return close + markerLen;
}

function readEmphasis(text: string, index: number): number | null {
  if (text[index] !== "*" || text.startsWith("**", index)) return null;
  if (text[index + 1] === " ") return null;
  const close = text.indexOf("*", index + 1);
  if (close < 0 || text.startsWith("**", close)) return null;
  const inner = text.slice(index + 1, close);
  if (!inner || inner.includes("\n")) return null;
  if (![...inner].some((char) => /[A-Za-z]/.test(char) && !isCjk(char))) return null;
  return close + 1;
}

function emit(out: string[], span: string, next: string): void {
  if (out.length > 0 && glueBefore(out[out.length - 1].slice(-1))) out.push(" ");
  out.push(span);
  if (glueAfter(next.slice(0, 1))) out.push(" ");
}

function leaveProseLine(line: string): boolean {
  if (line.startsWith("    ") || line.startsWith("\t")) return true;
  return line.trimStart().startsWith(">");
}

function repairLine(line: string): string {
  const out: string[] = [];
  let index = 0;
  while (index < line.length) {
    if (line[index] === "\\") {
      const end = skipCommand(line, index);
      out.push(line.slice(index, end));
      index = end;
      continue;
    }
    const urlEnd = readUrl(line, index);
    if (urlEnd != null) {
      out.push(line.slice(index, urlEnd));
      index = urlEnd;
      continue;
    }
    const readers = [readCode, readMath, readLink, readBold, readEmphasis];
    let matched = false;
    for (const reader of readers) {
      const end = reader(line, index);
      if (end == null) continue;
      emit(out, line.slice(index, end), line.slice(end, end + 1));
      index = end;
      matched = true;
      break;
    }
    if (matched) continue;
    if (line[index] === "*") {
      let cursor = index;
      while (cursor < line.length && line[cursor] === "*") cursor += 1;
      if (cursor - index >= 3 || cursor === line.length || /\s/.test(line[cursor] ?? "")) {
        out.push(line.slice(index, cursor));
        index = cursor;
        continue;
      }
    }
    out.push(line[index]);
    index += 1;
  }
  return out.join("");
}

function repairProse(prose: string): string {
  return prose
    .split("\n")
    .map((line) => (leaveProseLine(line) ? line : repairLine(line)))
    .join("\n");
}

export function repairInlineTokenBoundaries(text: string): string {
  return applyOutsideFences(text, repairProse);
}
