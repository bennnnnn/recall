import { escapedAt, readInlineCodeSpan } from "@/lib/markdown/inlineCode";

/**
 * The line a reply is still typing, with a bold it has opened closed where the stream has
 * got to: "1. **Demo" draws as "1. **Demo**", a bold name in bold from its first letter,
 * never "**Demo" with its asterisks showing until the closer arrives. A closer that has
 * come in part ("**Demo*", "***Note**") gets the stars it is missing, and a delimiter just
 * typed with nothing after it yet ("1. **", "1. *", "**Tip: 2 *") waits, so neither a pair
 * of asterisks nor an empty bullet flashes up.
 *
 * An italic opened inside it ("**Tip: 2 *r") is closed the same way, innermost first.
 * Stars pair as markdown-it pairs them (CommonMark's flanking rules), and a `**` between
 * two word characters ("2**10") opens nothing: with no partner yet, the settled line draws
 * it as typed. Only the last line is read: every line above it has ended, and its bold is
 * what the model wrote. Code is code, a span still typing too (it runs to the line's end,
 * as `prepareStreamingMathText` reads it). Maths spans arrive here with their stars
 * already protected.
 */
export function closeOpenBold(text: string): string {
  const lineStart = text.lastIndexOf("\n") + 1;
  const line = text.slice(lineStart);
  const closed = closeLineBold(line);
  return closed === line ? text : text.slice(0, lineStart) + closed;
}

const SPACE = /^\s$/u;
const PUNCT = /^[\p{P}\p{S}]$/u;
const WORD = /^[\p{L}\p{N}]$/u;

/** The character before `at`, a whole code point; "" at the line's start. */
function charBefore(line: string, at: number): string {
  if (at <= 0) return "";
  const low = line.charCodeAt(at - 1);
  const surrogate = low >= 0xdc00 && low <= 0xdfff && at >= 2;
  return line.slice(surrogate ? at - 2 : at - 1, at);
}

/** The character at `at`, a whole code point; "" past the line's end. */
function charAt(line: string, at: number): string {
  const code = line.codePointAt(at);
  return code === undefined ? "" : String.fromCodePoint(code);
}

type Run = { at: number; end: number; opens: boolean; closes: boolean };

/** A star run's place in CommonMark's pairing: the line's ends count as whitespace. */
function starRun(line: string, at: number): Run {
  let end = at;
  while (line[end] === "*") end += 1;
  const before = charBefore(line, at);
  const after = charAt(line, end);
  const spaceBefore = !before || SPACE.test(before);
  const spaceAfter = !after || SPACE.test(after);
  const left = !spaceAfter && (!PUNCT.test(after) || spaceBefore || PUNCT.test(before));
  const right = !spaceBefore && (!PUNCT.test(before) || spaceAfter || PUNCT.test(after));
  // Between two word characters a bold opens nothing until its partner comes.
  return { at, end, opens: left && !WORD.test(before), closes: right };
}

/**
 * The stars each opener still waits for, innermost last ("**Tip: 2 *r" waits for 2, then 1).
 * A closer run takes them from the innermost out; what it has over may open again.
 */
function pairRun(open: number[], run: Run): void {
  let stars = run.end - run.at;
  if (run.closes) {
    while (stars > 0 && open.length > 0) {
      const used = Math.min(stars, open[open.length - 1]!);
      stars -= used;
      open[open.length - 1]! -= used;
      if (open[open.length - 1] === 0) open.pop();
    }
  }
  if (stars > 0 && run.opens) open.push(Math.min(stars, 3));
}

/** `line` with the stars its openers still wait for, before any trailing space. */
function withClosers(line: string, open: number[]): string {
  const missing = open.reduce((sum, stars) => sum + stars, 0);
  if (!missing) return line;
  const body = line.replace(/\s+$/, "");
  return `${body}${"*".repeat(missing)}${line.slice(body.length)}`;
}

function closeLineBold(line: string): string {
  const open: number[] = [];
  let i = 0;
  while (i < line.length) {
    if (line[i] === "`" && !escapedAt(line, i)) {
      const end = readInlineCodeSpan(line, i);
      // A code span still typing runs to the line's end: nothing after its tick is bold.
      if (end == null) return line;
      i = end;
      continue;
    }
    if (line[i] !== "*" || escapedAt(line, i)) {
      i += 1;
      continue;
    }
    const run = starRun(line, i);
    // After a space, the line's last stars close nothing: they open what has not come yet,
    // so they wait ("1. **", "**Tip: 2 *").
    if (run.end === line.length && !run.closes) return withClosers(line.slice(0, run.at), open);
    pairRun(open, run);
    i = run.end;
  }
  return withClosers(line, open);
}
