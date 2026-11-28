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
 *   price tier, never maths, and so is one in brackets ("($$)") or one that ends a range
 *   ("$–$$");
 * - at the start of a line (after its indent, a quote mark or a list marker) it opens a
 *   formula that runs on over the lines below to the next `$$`;
 * - mid-line it is maths as `$$x$$`, nothing between the dollars and the formula, or as a
 *   padded `$$ x = 1 $$` that reads as maths, closed on the same line ("Californian,
 *   $$–$$$" and "Cafe – $$." are prices); or as a `$$` that ends a sentence's line
 *   ("Therefore: $$"), closed by a `$$` that starts a line before a blank line;
 * - a `$$` alone on its line, or with TeX after it, opens a block nothing but its closer
 *   ends: a line inside it that looks like a list item or a table row (`|x| < 5`,
 *   `- 3x &= 2`) is maths. One with words after it ("$$ = moderate") or in a list item
 *   reads as prose: a blank line, a list item or a table row ends it unclosed;
 * - a pair on a table row never spans a `|`.
 *
 * Inline code holds no maths: outside a formula a code span is skipped. Each line is read
 * once, left to right, so a line of many pairs costs its length.
 */
import { escapedAt, readInlineCodeSpan } from "@/lib/markdown/inlineCode";

/**
 * The closer a line leaves awaited, or none:
 * - `$$`: a block nothing but its closer ends;
 * - `$$ `: a formula opened in prose; a blank line, a list item or a table row ends it unclosed;
 * - `$$\n`: a formula opened at a line's end; only a `$$` that starts a line closes it, and
 *   a blank line ends it unclosed;
 * - `\]`: `\[ … \]` maths (read only when brackets are).
 */
export type DisplayCloser = "$$" | "$$ " | "$$\n" | "\\]" | null;

/** Something a formula is made of, in any script ("π", "∞"); "–" or ", " is not one. */
const FORMULA_CHAR_RE = /[\p{L}\p{N}\\∞]/u;
/** Text after an opening `$$` that is TeX, not words. */
const TEX_RE = /[\\^_{}]/;
/** A mark only maths writes: a relation, a script, a command, a bar. */
const MATH_MARK_RE = /[=<>^_\\|]/;
/** A TeX group of words (`\text{Total cost}`, `\mathrm{ m/s}`): a formula's unit or label. */
const WORD_GROUP_RE = /\\(?:text|textrm|textbf|textit|mathrm|mathbf|mathit|mbox|operatorname)\s*\{[^{}]*\}/g;
/** A TeX command and the environment name after it (`\begin{aligned}`). */
const COMMAND_RE = /\\[A-Za-z]+(?:\{[A-Za-z*]*\})?/g;

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

/** Where a delimiter stands at a line's start: after its indent and quote marks, and after a
 * list marker there too (-1 when there is none). Read once per line. */
type LineStarts = { line: number; item: number };

function lineStarts(line: string): LineStarts {
  let at = afterBlanks(line);
  while (line[at] === ">") {
    at += 1;
    if (line[at] === " " || line[at] === "\t") at += 1;
  }
  return { line: at, item: afterListMarker(line, at) };
}

/** Whether a delimiter at `index` stands at its line's start, and after a list marker. */
function startKind(starts: LineStarts, index: number): false | "line" | "item" {
  if (index === starts.line) return "line";
  return index === starts.item ? "item" : false;
}

/** The last character of `line` that is not a blank, or -1. */
function lastText(line: string): number {
  let at = line.length - 1;
  while (at >= 0 && /\s/.test(line[at]!)) at -= 1;
  return at;
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

/** A dash that joins two price tiers ("$–$$", "$$-$$$"), en and em dashes included. */
const RANGE_DASHES = "-–—";
/** What may come before a price tier: the line's start, a blank or an opening mark. */
const TIER_BEFORE = " \t(,:;";

/**
 * The run of two at `start` ends a price range, `$–$$` or `$ – $$`: a dash before it and a
 * tier before the dash that starts a word, with no blank between unless that tier is a lone `$`
 * (never a delimiter). "Burmese, $–$$" at a line's end opened a formula there (2026-11-27).
 */
function rangeEnd(line: string, start: number): boolean {
  let at = start - 1;
  while (at >= 0 && /[ \t]/.test(line[at]!)) at -= 1;
  const spaced = at < start - 1;
  if (at < 0 || !RANGE_DASHES.includes(line[at]!)) return false;
  at -= 1;
  const dash = at;
  while (at >= 0 && /[ \t]/.test(line[at]!)) at -= 1;
  if (line[at] !== "$") return false;
  let first = at;
  while (first > 0 && line[first - 1] === "$") first -= 1;
  // A tier starts a word: "$a$ — $$b$$" closes a formula with its "$", which is no tier.
  if (first > 0 && !TIER_BEFORE.includes(line[first - 1]!)) return false;
  return first === at || (!spaced && at === dash);
}

/**
 * Words of three letters or more, TeX aside (word groups whatever they hold, commands and
 * their environment names): "a night, and suites" holds two, "v = 20 \text{ meters per
 * second}" none.
 */
function proseWords(text: string): number {
  const tex = text.replace(WORD_GROUP_RE, " ").replace(COMMAND_RE, " ");
  return (tex.match(/[A-Za-z]{3,}/g) ?? []).length;
}

/** A padded mid-line pair's text that is a formula: a maths mark, and words at most one. */
function paddedFormula(body: string): boolean {
  return MATH_MARK_RE.test(body) && proseWords(body) < 2;
}

/**
 * The closer of a mid-line pair whose opener ends at `from`, on the same line: the next run
 * of exactly two. Tight on both sides (`$$x$$`, `$$π$$`), any formula; padded on either side
 * (`$$ x = 1 $$`, `$$x = 1 $$`), only one that reads as maths, not words ("Rooms are $$ a
 * night, and suites $$ more.", "$$, and Zuni $$"). Null when none closes.
 */
function tightCloser(line: string, from: number, table: boolean): number | null {
  if (from >= line.length || line[from] === "$") return null;
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
      if (/^\s|\s$/.test(body) && !paddedFormula(body)) return null;
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

/**
 * Whether `line` ends a formula `closer` awaits, unclosed, before it is read. One opened in
 * prose ends at a blank line, a list item or a table row; one opened at a line's end, whose
 * formula lines may start like a row or an item ("|x - 3| < 5", "+ 2x + 1"), at a blank line.
 */
function endsUnclosed(line: string, closer: DisplayCloser): boolean {
  if (closer === "$$ ") return !line.trim() || startsItemOrRow(line);
  if (closer === "$$\n") return !line.trim();
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
  const starts = lineStarts(line);
  const last = lastText(line);
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
      if (end - index === 2 && closer !== "\\]" && !bracketedTier(line, index, end) && !rangeEnd(line, index)) {
        const start = startKind(starts, index);
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
          if (end > last) {
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

/** What one read of a text found: each formula's end by its start, the formula still open
 * at the text's end, and the offsets that are a line's start. */
type Reading = {
  text: string;
  ends: Map<number, number>;
  openStart: number | null;
  lineStarts: Set<number>;
  /** Where the text's last line starts: the line still being written while it streams. */
  lastLine: number;
};

/** Read `text` (prose, no fences) once, line by line, carrying what each line leaves open. */
function readText(text: string): Reading {
  const ends = new Map<number, number>();
  const starts = new Set<number>();
  let closer: DisplayCloser = null;
  let openAt = -1;
  let lineStart = 0;
  while (lineStart <= text.length) {
    const nl = text.indexOf("\n", lineStart);
    const line = text.slice(lineStart, nl < 0 ? text.length : nl);
    const offset = lineStart;
    const here = lineStarts(line);
    starts.add(offset + here.line);
    if (here.item >= 0) starts.add(offset + here.item);
    closer = scanDisplayLine(line, closer, false, (kind, at) => {
      if (kind === "open") openAt = offset + at;
      else if (kind === "close") ends.set(openAt, offset + at + 2);
    });
    if (nl < 0) break;
    lineStart = nl + 1;
  }
  const openStart = awaitsDollars(closer) ? openAt : null;
  return { text, ends, openStart, lineStarts: starts, lastLine: lineStart };
}

/**
 * The last text read, kept while readers ask about each of its `$$` in turn: an inline reader
 * asks once per delimiter, so one read serves a line of many pairs. Sign-out clears it.
 */
let lastReading: Reading | null = null;

function reading(text: string): Reading {
  if (lastReading?.text !== text) lastReading = readText(text);
  return lastReading;
}

/** Sign-out: the text last read was the account's. */
export function clearDisplayDollarsMemo(): void {
  lastReading = null;
}

/** Each display formula in `text` (prose, no fences): from its opening to past its closing `$$`. */
export function findDisplayDollars(text: string): { start: number; end: number }[] {
  return [...reading(text).ends].map(([start, end]) => ({ start, end }));
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
 * question: a table cell, a card's text, the streaming line). Read as the whole text reads,
 * so code spans and earlier pairs are read as they are. Null when no formula opens there,
 * or it is not closed.
 */
export function displayDollarPairEnd(text: string, start: number): number | null {
  return reading(text).ends.get(start) ?? null;
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
  const read = reading(text);
  if (read.openStart === start) return true;
  // A `$$x` on the line still being written may find its closer. A padded `$$ x = 1 $$`
  // waits for nothing: it shows as typed until its closer comes, so a price never holds the line.
  return end > read.lastLine && FORMULA_CHAR_RE.test(text[end]!) && !read.lineStarts.has(start);
}

function runStartsAt(text: string, start: number): boolean {
  if (text[start] !== "$" || escapedAt(text, start)) return false;
  return !(text[start - 1] === "$" && !escapedAt(text, start - 1));
}
