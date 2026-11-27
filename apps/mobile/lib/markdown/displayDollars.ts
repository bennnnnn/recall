/**
 * `$$` display maths, as every reader on the phone reads it: the conversion to a maths
 * card (`convertBlockMath`), the presentation passes (`displayMathLines`), the inline
 * readers (`readInlineMathSpan`), the passes that leave maths alone (`codeNotation`,
 * `normalizeImplicitMath`) and the streaming scanners. The API's twin is
 * apps/api/app/modules/chat/display_dollars.py; docs/fixtures/display_math_cases.json holds
 * the two to one answer.
 *
 * remark-math's rule, as a reader reads a price list:
 * - a delimiter is a run of exactly two unescaped dollars: three or more ("$$$") are a
 *   price tier, never maths, and so is one in brackets ("($$)");
 * - at the start of a line (after its indent, a quote mark or a list marker) it opens a
 *   formula that runs on over the lines below to the next `$$`;
 * - mid-line it is maths as `$$x$$`, nothing between the dollars and the formula, closed
 *   on the same line ("Californian, $$–$$$" and "Cafe – $$." are prices), or as a `$$`
 *   that ends a sentence's line ("Therefore: $$"), closed by a `$$` that starts a line
 *   before a blank line;
 * - a `$$` alone on its line, or with TeX after it, opens a block nothing but its closer
 *   ends: a line inside it that looks like a list item or a table row (`|x| < 5`,
 *   `- 3x &= 2`) is maths. One with words after it ("$$ = moderate") or in a list item
 *   reads as prose: a list item or a table row ends it unclosed.
 * - a pair on a table row never spans a `|`.
 *
 * Inline code holds no maths: outside a formula a code span is skipped.
 */
import { escapedAt, readInlineCodeSpan } from "@/lib/markdown/inlineCode";

/**
 * The closer a line leaves awaited, or none:
 * - `$$`: a block nothing but its closer ends;
 * - `$$ `: a formula opened in prose; a list item or a table row ends it unclosed;
 * - `$$\n`: a formula opened at a line's end; only a `$$` that starts a line closes it, and
 *   a blank line, a list item or a table row ends it unclosed;
 * - `\]`: `\[ … \]` maths (read only when brackets are).
 */
export type DisplayCloser = "$$" | "$$ " | "$$\n" | "\\]" | null;

/** Something a formula is made of; "–" or ", " between two dollar pairs is not one. */
const FORMULA_CHAR_RE = /[A-Za-z0-9\\]/;
/** Text after an opening `$$` that is TeX, not words. */
const TEX_RE = /[\\^_{}]/;
/** A mark only maths writes: a relation, a script, a command, a bar. */
const MATH_MARK_RE = /[=<>^_\\|]/;

/** Awaiting a `$$` closer, of any kind. */
function awaitsDollars(closer: DisplayCloser): boolean {
  return closer === "$$" || closer === "$$ " || closer === "$$\n";
}

/** After `text`'s spaces and tabs from `at`. A loop, so no pattern reads a run twice. */
function afterBlanks(text: string, at = 0): number {
  while (text[at] === " " || text[at] === "\t") at += 1;
  return at;
}

/** After a list marker at `at` and the blanks it needs: `-`, `*`, `+`, `1.`, `1)`; or -1. */
function afterListMarker(text: string, at: number): number {
  let end = at;
  if (text[end] === "-" || text[end] === "*" || text[end] === "+") end += 1;
  else {
    while (end - at < 9 && text[end]! >= "0" && text[end]! <= "9") end += 1;
    if (end === at || (text[end] !== "." && text[end] !== ")")) return -1;
    end += 1;
  }
  const blanks = afterBlanks(text, end);
  return blanks > end ? blanks : -1;
}

/**
 * Whether `prefix` (a line's text before a delimiter) is the line's start: its indent,
 * quote marks and a list marker. "item" when the list marker is there.
 */
function readLineStart(prefix: string): false | "line" | "item" {
  let at = afterBlanks(prefix);
  while (prefix[at] === ">") {
    at += 1;
    if (prefix[at] === " " || prefix[at] === "\t") at += 1;
  }
  if (at === prefix.length) return "line";
  const marker = afterListMarker(prefix, at);
  return marker === prefix.length ? "item" : false;
}

/** A list item or a table row: a formula opened in prose ends before it. */
function startsItemOrRow(line: string): boolean {
  const at = afterBlanks(line);
  return line[at] === "|" || afterListMarker(line, at) > 0;
}

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
  let before = start - 1;
  while (before >= 0 && /\s/.test(line[before]!)) before -= 1;
  let after = end;
  while (after < line.length && /\s/.test(line[after]!)) after += 1;
  return line[before] === "(" && line[after] === ")";
}

/** Words of three letters or more, TeX commands aside: "a night, and suites" holds two. */
function proseWords(text: string): number {
  return (text.replace(/\\[A-Za-z]+(?:\{[A-Za-z*]*\})?/g, " ").match(/[A-Za-z]{3,}/g) ?? []).length;
}

/** A padded mid-line pair's text that is a formula: a maths mark, and words at most one. */
function paddedFormula(body: string): boolean {
  return MATH_MARK_RE.test(body) && proseWords(body) < 2;
}

/**
 * The closer of a mid-line pair whose opener ends at `from`, on the same line: the next run
 * of exactly two. Tight (`$$x$$`), any formula; padded (`$$ x = 1 $$`), only one that reads
 * as maths, not words ("Rooms are $$ a night, and suites $$ more."). Null when none closes.
 */
function tightCloser(line: string, from: number, table: boolean): number | null {
  if (from >= line.length || line[from] === "$") return null;
  const padded = /\s/.test(line[from]!);
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
      if (!FORMULA_CHAR_RE.test(body) || bracketedTier(line, i, end)) return null;
      if (padded ? !paddedFormula(body) : /\s$/.test(body)) return null;
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

/** The formula a `$$` at the start of a line opens: a block, or one read as prose. */
function lineOpener(line: string, end: number, start: "line" | "item"): DisplayCloser {
  const rest = line.slice(end).trim();
  return start === "line" && (!rest || TEX_RE.test(rest)) ? "$$" : "$$ ";
}

/** Whether `line` ends a formula `closer` awaits, unclosed, before it is read. */
function endsUnclosed(line: string, closer: DisplayCloser): boolean {
  if (closer === "$$ ") return startsItemOrRow(line);
  if (closer === "$$\n") return !line.trim() || startsItemOrRow(line);
  return false;
}

/**
 * The closer still awaited after `line`, given the one awaited before it. With `brackets`,
 * `\[ … \]` is read too (a `$$` inside one is its text). `emit` hears each `$$` delimiter
 * by its offset in the line, and a formula a line ended unclosed.
 */
export function scanDisplayLine(
  line: string,
  before: DisplayCloser,
  brackets = false,
  emit?: DisplayEvent,
): DisplayCloser {
  let closer = before;
  if (endsUnclosed(line, closer)) {
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
        const start = readLineStart(line.slice(0, index));
        if (awaitsDollars(closer)) {
          // A formula opened at a line's end closes only at a line's start.
          if (closer !== "$$\n" || start) {
            closer = null;
            emit?.("close", index);
          }
        } else if (start) {
          closer = lineOpener(line, end, start);
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
          if (!line.slice(end).trim()) {
            closer = "$$\n";
            emit?.("open", index);
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

/** The `$$` formula awaited after `line`, given the one awaited before it (null: none). */
export function displayDollarsAfter(line: string, before: DisplayCloser): DisplayCloser {
  return scanDisplayLine(line, before);
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
 * The maths a pass leaves alone in `text`: each `$$` formula, and each match of `others`
 * (a global pattern: code, `$…$`, `\(…\)`), left to right, none inside another.
 */
export function mathSpans(text: string, others: RegExp): { start: number; end: number }[] {
  const dollars = findDisplayDollars(text);
  const spans: { start: number; end: number }[] = [];
  let at = 0;
  let next = 0;
  while (at <= text.length) {
    while (next < dollars.length && dollars[next]!.start < at) next += 1;
    others.lastIndex = at;
    const match = others.exec(text);
    const dollar = dollars[next];
    if (!match && !dollar) break;
    const span = dollar && (!match || dollar.start <= match.index)
      ? dollar
      : { start: match!.index, end: match!.index + Math.max(1, match![0].length) };
    spans.push(span);
    at = span.end;
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
 * "Cafe – $$. Great" and "$$–$$$" are prices: nothing waits for them.
 */
export function displayDollarsMayOpen(text: string, start: number): boolean {
  if (!runStartsAt(text, start)) return false;
  const end = runEnd(text, start);
  if (end === text.length) return end - start <= 2;
  if (end - start !== 2) return false;
  if (readFormulaAt(text, start).open) return true;
  // A `$$x` on the line still being written may find its closer. A padded `$$ x = 1 $$`
  // waits for nothing: it shows as typed until its closer comes, so a price never holds the line.
  return text.indexOf("\n", end) < 0 && FORMULA_CHAR_RE.test(text[end]!) && !readLineStart(lineBefore(text, start));
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
