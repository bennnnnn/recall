/**
 * `$$` display maths, as every reader on the phone reads it: the conversion to a maths
 * card (`convertBlockMath`), the presentation passes (`displayMathLines`), the inline
 * readers (`readInlineMathSpan`) and the streaming scanners. The API's twin is
 * apps/api/app/modules/chat/display_dollars.py; docs/fixtures/display_math_cases.json holds
 * the two to one answer.
 *
 * remark-math's rule, as a reader reads a price list:
 * - a delimiter is a run of exactly two unescaped dollars: three or more ("$$$") are a
 *   price tier, never maths, and so is one in brackets ("($$)");
 * - it opens display maths at the start of a line (after its indent, a quote mark or a
 *   list marker), and the formula may run on over the lines below to the next `$$`;
 * - mid-line it is maths only as `$$x$$`, nothing between the dollars and the formula,
 *   closed on the same line ("Californian, $$–$$$" and "Cafe – $$." are prices);
 * - a formula never reaches across a list item or a table row, and a pair on a table
 *   row never spans a `|`.
 *
 * Inline code holds no maths: outside a formula a code span is skipped.
 */
import { escapedAt, readInlineCodeSpan } from "@/lib/markdown/inlineCode";

/** The closer a line leaves awaited: `$$`, `\]` (only when brackets are read), or none. */
export type DisplayCloser = "$$" | "\\]" | null;

/** A line's text before a delimiter that still counts as the line's start. */
const LINE_START_RE = /^[ \t]*(?:>[ \t]?)*(?:(?:[-*+]|\d{1,9}[.)])[ \t]+)?$/;
/** A line that starts a list item or a table row: an open formula ends before it. */
const ENDS_FORMULA_RE = /^[ \t]*(?:(?:[-*+]|\d{1,9}[.)])[ \t]|\|)/;
/** Something a formula is made of; "–" or ", " between two dollar pairs is not one. */
const FORMULA_CHAR_RE = /[A-Za-z0-9\\]/;

function isTableRow(line: string): boolean {
  return line.trimStart().startsWith("|");
}

/** The run of dollars at `at` (at its first dollar): its end. */
function runEnd(text: string, at: number): number {
  let end = at;
  while (text[end] === "$") end += 1;
  return end;
}

/** A price tier in brackets, "( $$ )": no delimiter. */
function bracketedTier(line: string, start: number, end: number): boolean {
  return /\(\s*$/.test(line.slice(0, start)) && /^\s*\)/.test(line.slice(end));
}

/**
 * The closer of a `$$x$$` pair whose opener ends at `from`, on the same line: the next
 * run of exactly two, right after the formula. Null when the line holds none.
 */
function tightCloser(line: string, from: number, table: boolean): number | null {
  if (from >= line.length || /\s/.test(line[from]!) || line[from] === "$") return null;
  let slashes = 0;
  for (let i = from; i < line.length; ) {
    if (line[i] === "$" && slashes % 2 === 0) {
      const end = runEnd(line, i);
      if (end - i !== 2) {
        // A lone dollar may sit inside the formula; a longer run ends the hope of one.
        if (end - i > 2) return null;
        i = end;
        slashes = 0;
        continue;
      }
      const body = line.slice(from, i);
      if (/\s$/.test(body) || !FORMULA_CHAR_RE.test(body) || bracketedTier(line, i, end)) return null;
      if (table && body.includes("|")) return null;
      return i;
    }
    slashes = line[i] === "\\" ? slashes + 1 : 0;
    i += 1;
  }
  return null;
}

/** What a scan reports: a formula opened, closed, or one left open dropped (`at` -1). */
type DisplayEvent = (kind: "open" | "close" | "drop", at: number) => void;

/**
 * The closer still awaited after `line`, given the one awaited before it. With `brackets`,
 * `\[ … \]` is read too (a `$$` inside one is its text). `emit` hears each `$$` delimiter
 * by its offset in the line, and a formula a list item or table row ended unclosed.
 */
export function scanDisplayLine(
  line: string,
  before: DisplayCloser,
  brackets = false,
  emit?: DisplayEvent,
): DisplayCloser {
  let closer = before;
  if (closer === "$$" && ENDS_FORMULA_RE.test(line)) {
    closer = null;
    emit?.("drop", -1);
  }
  if (!line.includes("$") && !(brackets && line.includes("\\"))) return closer;
  const table = isTableRow(line);
  let index = 0;
  // The backslashes just before `index`, counted as the scan passes them: an odd run
  // escapes the character there.
  let slashes = 0;
  while (index < line.length) {
    const char = line[index];
    const codeEnd = closer == null && char === "`" ? readInlineCodeSpan(line, index) : null;
    if (codeEnd != null) {
      index = codeEnd;
      slashes = 0;
      continue;
    }
    if (char === "$" && slashes % 2 === 0) {
      const end = runEnd(line, index);
      if (end - index === 2 && closer !== "\\]" && !bracketedTier(line, index, end)) {
        if (closer === "$$") {
          closer = null;
          emit?.("close", index);
        } else if (LINE_START_RE.test(line.slice(0, index))) {
          closer = "$$";
          emit?.("open", index);
        } else {
          const close = tightCloser(line, end, table);
          if (close != null) {
            emit?.("open", index);
            emit?.("close", close);
            index = close + 2;
            slashes = 0;
            continue;
          }
        }
      }
      index = end;
      slashes = 0;
      continue;
    }
    if (brackets && slashes % 2 === 0 && char === "\\") {
      const next = line[index + 1];
      if (next === "[" && closer == null) {
        closer = "\\]";
        index += 2;
        slashes = 0;
        continue;
      }
      if (next === "]" && closer === "\\]") {
        closer = null;
        index += 2;
        slashes = 0;
        continue;
      }
    }
    slashes = char === "\\" ? slashes + 1 : 0;
    index += 1;
  }
  return closer;
}

/** Whether a `$$` formula is still open after `line`, given whether one was before it. */
export function dollarDisplayOpenAfter(line: string, open: boolean): boolean {
  return scanDisplayLine(line, open ? "$$" : null) === "$$";
}

/** Each display formula in `text` (prose, no fences): from its opening to past its closing `$$`. */
export function findDisplayDollars(text: string): { start: number; end: number }[] {
  const spans: { start: number; end: number }[] = [];
  let closer: DisplayCloser = null;
  let openAt = -1;
  let lineStart = 0;
  while (lineStart <= text.length) {
    const nl = text.indexOf("\n", lineStart);
    const lineEnd = nl < 0 ? text.length : nl;
    const offset = lineStart;
    closer = scanDisplayLine(text.slice(lineStart, lineEnd), closer, false, (kind, at) => {
      if (kind === "open") openAt = offset + at;
      else if (kind === "close") spans.push({ start: openAt, end: offset + at + 2 });
    });
    if (nl < 0) break;
    lineStart = nl + 1;
  }
  return spans;
}

/**
 * The end of the `$$` formula whose opener is at `start` in `text` (an inline reader's
 * question: a table cell, a card's text, the streaming line). The formula is read from its
 * line's start, so code spans and earlier pairs on the line are read as they are. Null when
 * no formula opens there, or it is not closed.
 */
export function displayDollarPairEnd(text: string, start: number): number | null {
  return readFormulaAt(text, start).end;
}

/**
 * Whether the dollars at `start` in a reply still streaming may yet open a formula: one
 * opened there and not closed, a `$$x` whose line is still being written, or a run of one
 * or two dollars that ends the text so far (it may grow into a delimiter or a price tier).
 */
export function displayDollarsMayOpen(text: string, start: number): boolean {
  if (!runStartsAt(text, start)) return false;
  const end = runEnd(text, start);
  if (end === text.length) return end - start <= 2;
  if (end - start !== 2) return false;
  if (readFormulaAt(text, start).open) return true;
  // A `$$x` on the line still being written may find its closer.
  return text.indexOf("\n", end) < 0 && !/\s/.test(text[end]!) && !LINE_START_RE.test(lineBefore(text, start));
}

function runStartsAt(text: string, start: number): boolean {
  if (text[start] !== "$" || escapedAt(text, start)) return false;
  return !(text[start - 1] === "$" && !escapedAt(text, start - 1));
}

function lineBefore(text: string, at: number): string {
  return text.slice(text.lastIndexOf("\n", at - 1) + 1, at);
}

/** The formula opened at `start`: its end when it closed, or whether it is still open. */
function readFormulaAt(text: string, start: number): { end: number | null; open: boolean } {
  if (!runStartsAt(text, start)) return { end: null, open: false };
  let lineStart = text.lastIndexOf("\n", start - 1) + 1;
  let closer: DisplayCloser = null;
  let opened = false;
  let end: number | null = null;
  let dropped = false;
  for (;;) {
    const nl = text.indexOf("\n", lineStart);
    const offset = lineStart;
    const line = text.slice(lineStart, nl < 0 ? text.length : nl);
    closer = scanDisplayLine(line, closer, false, (kind, at) => {
      if (end != null || dropped) return;
      if (kind === "open" && !opened) opened = offset + at === start;
      else if (kind === "close" && opened) end = offset + at + 2;
      else if (kind === "drop" && opened) dropped = true;
    });
    // Nothing opened at `start` on its own line, or its formula ended: done.
    if (end != null || dropped || !opened || closer == null) return { end, open: false };
    if (nl < 0) return { end: null, open: true };
    lineStart = nl + 1;
  }
}
