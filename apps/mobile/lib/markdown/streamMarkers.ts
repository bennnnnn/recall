import { escapedAt, readInlineCodeSpan } from "@/lib/markdown/inlineCode";
import { markdownItInstance } from "@/lib/markdown/parser";

/**
 * The line a reply is still typing, with the emphasis stars that have no partner yet left
 * out: "1. **Demo" draws "1. Demo", plain, and turns bold where its closer lands; never
 * "**Demo" with its asterisks showing meanwhile. Nothing is added, so nothing is drawn
 * bold that the finished line does not draw bold. An opener that never gets its partner
 * ("Use **kwargs to …") shows its word plain while it types and `**kwargs` once the line
 * ends, as markdown draws it.
 *
 * Stars pair as markdown-it pairs them (`scanDelims`, `processDelimiters`). The stars that
 * end the line are still arriving ("**Demo*", "**Given:**" just before its next word, the
 * first "*" of an opener) and wait with them. Code is code, closed or still typing (an
 * unclosed tick runs to the line's end, as `prepareStreamingMathText` reads it); maths
 * spans arrive here with their stars protected. Only the last line is read: every line
 * above it has ended.
 */
export function hideUnpairedMarkers(text: string): string {
  const lineStart = text.lastIndexOf("\n") + 1;
  const line = text.slice(lineStart);
  if (!line.includes("*")) return text;
  const shown = lineWithoutUnpaired(line);
  return shown === line ? text : text.slice(0, lineStart) + shown;
}

const { isMdAsciiPunct, isPunctCharCode, isWhiteSpace } = markdownItInstance.utils;

/** One `*` of a run, as markdown-it's emphasis rule records it. */
type Star = {
  at: number;
  /** The whole run's length, which the rule of three reads. */
  length: number;
  token: number;
  open: boolean;
  close: boolean;
  /** The star it pairs with, or -1. */
  end: number;
  paired: boolean;
  /**
   * Whether markdown-it could read it as a marker at all, so hiding it unpaired hides
   * nothing the finished line shows: not "2 * 3", and not "2**10", a run inside a word.
   */
  marker: boolean;
};

function codeBefore(line: string, at: number): number {
  if (at <= 0) return 32;
  const code = line.codePointAt(at - 1) ?? 32;
  if (at >= 2 && code >= 0xdc00 && code <= 0xdfff) return line.codePointAt(at - 2) ?? 32;
  return code;
}

function punct(code: number): boolean {
  return isMdAsciiPunct(code) || isPunctCharCode(code);
}

/** The stars of one run, flanking read as markdown-it's `scanDelims` reads it. */
function runStars(line: string, at: number, end: number, token: number): Star[] {
  const last = codeBefore(line, at);
  const next = end < line.length ? (line.codePointAt(end) ?? 32) : 32;
  const left = !isWhiteSpace(next) && (!punct(next) || isWhiteSpace(last) || punct(last));
  const right = !isWhiteSpace(last) && (!punct(last) || isWhiteSpace(next) || punct(next));
  const inWord = left && right && !punct(last) && !punct(next);
  return Array.from({ length: end - at }, (_, i) => ({
    at: at + i,
    length: end - at,
    token: token + i,
    open: left,
    close: right,
    end: -1,
    paired: false,
    marker: (left || right) && !inWord,
  }));
}

/** The stars a line holds outside code, its last run (still arriving) left out. */
function lineStars(line: string, from: number): { stars: Star[]; waiting: number } {
  const stars: Star[] = [];
  let token = 0;
  let i = from;
  let waiting = line.length;
  while (i < line.length) {
    if (line[i] === "`" && !escapedAt(line, i)) {
      const end = readInlineCodeSpan(line, i);
      // Still typing, the span runs to the line's end: nothing after its tick is a marker.
      if (end == null) break;
      i = end;
      continue;
    }
    if (line[i] !== "*" || escapedAt(line, i)) {
      i += 1;
      continue;
    }
    let end = i;
    while (line[end] === "*") end += 1;
    if (end === line.length) {
      waiting = i;
      break;
    }
    stars.push(...runStars(line, i, end, token));
    token += end - i + 1;
    i = end;
  }
  return { stars, waiting };
}

/** markdown-it's `processDelimiters` for `*`, marking the stars that pair. */
function pairStars(stars: Star[]): void {
  const openersBottom = [-1, -1, -1, -1, -1, -1];
  const jumps: number[] = [];
  let headerIdx = 0;
  let lastToken = -2;
  for (let closerIdx = 0; closerIdx < stars.length; closerIdx += 1) {
    const closer = stars[closerIdx]!;
    jumps.push(0);
    if (lastToken !== closer.token - 1) headerIdx = closerIdx;
    lastToken = closer.token;
    if (!closer.close) continue;
    const bottom = (closer.open ? 3 : 0) + (closer.length % 3);
    let openerIdx = headerIdx - jumps[headerIdx]! - 1;
    let newMin = openerIdx;
    for (; openerIdx > openersBottom[bottom]!; openerIdx -= jumps[openerIdx]! + 1) {
      const opener = stars[openerIdx]!;
      if (!opener.open || opener.end >= 0) continue;
      const odd =
        (opener.close || closer.open) &&
        (opener.length + closer.length) % 3 === 0 &&
        (opener.length % 3 !== 0 || closer.length % 3 !== 0);
      if (odd) continue;
      const lastJump = openerIdx > 0 && !stars[openerIdx - 1]!.open ? jumps[openerIdx - 1]! + 1 : 0;
      jumps[closerIdx] = closerIdx - openerIdx + lastJump;
      jumps[openerIdx] = lastJump;
      closer.open = false;
      opener.end = closerIdx;
      opener.close = false;
      opener.paired = true;
      closer.paired = true;
      newMin = -1;
      lastToken = -2;
      break;
    }
    if (newMin !== -1) openersBottom[(closer.open ? 3 : 0) + (closer.length % 3)] = newMin;
  }
}

/** Where a line's text starts after its indent and block markers (list, heading, quote). */
const BLOCK_PREFIX = /^[ \t]*(?:(?:\d{1,9}[.)]|[-+*]|#{1,6}|>)[ \t]+)*/;
/** A zero-width space: what a hidden opener leaves where its removal would start a block. */
const HOLD_PLACE = "\u200b";

/** A list, heading or quote marker that hidden stars at the line's start would uncover. */
const BLOCK_START = /^(?:\d{1,9}[.)]|[-+*]|#{1,6}|>)(?:[ \t]|$)/;

function opensBlock(line: string, at: number, hidden: Set<number>): boolean {
  let after = at;
  while (hidden.has(after)) after += 1;
  return BLOCK_START.test(line.slice(after));
}

function lineWithoutUnpaired(line: string): string {
  // A bullet's own star is no marker: read from where the line's text starts.
  const contentStart = BLOCK_PREFIX.exec(line)?.[0].length ?? 0;
  const { stars, waiting } = lineStars(line, contentStart);
  pairStars(stars);
  const hidden = new Set(stars.filter((star) => star.marker && !star.paired).map((star) => star.at));
  if (!hidden.size && waiting === line.length) return line;
  let out = "";
  for (let i = 0; i < waiting; i += 1) {
    if (!hidden.has(i)) out += line[i];
    // "**1. Subtract" must not draw as a numbered list while its closer is on its way.
    else if (i === contentStart && opensBlock(line, i, hidden)) out += HOLD_PLACE;
  }
  return out;
}
