import { escapedAt, readInlineCodeSpan } from "@/lib/markdown/inlineCode";

/**
 * The line a reply is still typing, with a bold it has opened closed where the stream has
 * got to: "1. **Demo" draws as "1. **Demo**", a bold name in bold from its first letter,
 * never "**Demo" with its asterisks showing until the closer arrives. Half a closer
 * ("**Demo*") gets its other half, and a delimiter just typed with nothing after it yet
 * ("1. **", "1. *") waits, so neither a pair of asterisks nor an empty bullet flashes up.
 *
 * Only the last line is read: every line above it has ended, and its bold is what the
 * model wrote. Code spans are code. Maths spans arrive here with their stars already
 * protected (`prepareStreamingMathText`).
 */
export function closeOpenBold(text: string): string {
  const lineStart = text.lastIndexOf("\n") + 1;
  const line = text.slice(lineStart);
  const closed = closeLineBold(line);
  return closed === line ? text : text.slice(0, lineStart) + closed;
}

const SPACE = /\s/;

function closeLineBold(line: string): string {
  let open: { at: number; length: number } | null = null;
  let i = 0;
  while (i < line.length) {
    if (line[i] === "`") {
      i = readInlineCodeSpan(line, i) ?? i + 1;
      continue;
    }
    if (line[i] !== "*" || escapedAt(line, i)) {
      i += 1;
      continue;
    }
    let end = i;
    while (line[end] === "*") end += 1;
    const before = line[i - 1] ?? "";
    const after = line[end] ?? "";
    if (!after && !open && (end - i >= 2 || !before || SPACE.test(before))) {
      // Just typed, nothing after it yet: it opens something not here yet.
      return line.slice(0, i);
    }
    if (end - i >= 2) {
      // As markdown-it pairs them: a closer touches the text before it, an opener the text after.
      if (open && before && !SPACE.test(before)) open = null;
      else if (!open && after && !SPACE.test(after)) open = { at: i, length: Math.min(end - i, 3) };
    }
    i = end;
  }
  if (!open) return line;
  // "**Demo*": the closer's first half is here.
  if (line.endsWith("*") && !line.endsWith("**") && line.length - 1 > open.at + open.length) {
    return `${line}${"*".repeat(open.length - 1)}`;
  }
  const body = line.replace(/\s+$/, "");
  return `${body}${"*".repeat(open.length)}${line.slice(body.length)}`;
}
