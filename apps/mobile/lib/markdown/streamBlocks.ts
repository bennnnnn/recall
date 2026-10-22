/**
 * Append-only chunking of streaming markdown so settled text parses once.
 *
 * The streaming renderer re-parsed the whole reply on every flush and
 * react-native-markdown-display regenerates node keys per parse, so the
 * entire message subtree remounted every time — jankier the longer the
 * reply. Splitting the prepared text into settled chunks (each rendered by
 * its own memoized `<Markdown>`) plus a small growing tail keeps per-flush
 * work proportional to the tail, ChatGPT-style.
 *
 * Chunks only ever append while the same reply streams; each chunk's string
 * never changes, so its parse/render is done exactly once.
 */

import {
  CONTINUATION_LINE_RE,
  listGoesOn,
  listItemCut,
  type OpenList,
} from "@/lib/markdown/streamListCuts";

export type { OpenList } from "@/lib/markdown/streamListCuts";

export type StreamBlocksState = {
  /** Settled chunks; their concatenation is exactly `settledText`. */
  chunks: string[];
  /**
   * Per chunk: it ends between two items of one list, so its last list
   * continues in the next chunk and is drawn without a list's end (see
   * `markdownRenderRules`).
   */
  continued: boolean[];
  /** Per chunk: the list still open where it ends. */
  listAfter: (OpenList | null)[];
  /** Prefix of the prepared streaming text covered by `chunks`. */
  settledText: string;
};

/** Group small blocks together so long replies don't spawn hundreds of renderers. */
export const MIN_SETTLED_CHUNK_CHARS = 320;

const LIST_LINE_RE = /^ {0,3}(?:[-*+]|\d{1,9}[.)])(?:\s|$)/;
const TABLE_LINE_RE = /^ {0,3}\|/;
const QUOTE_LINE_RE = /^ {0,3}>/;
const FENCE_LINE_RE = /^(?:```|~~~)/;

function isBlankLine(line: string): boolean {
  return line.trim().length === 0;
}

/**
 * Lines that glue to their neighbours across blank lines: cutting before them
 * would split a list, table or quote, or detach a list continuation into a
 * separate parse. (Between two items of one list is the one exception; see
 * `listItemCut`.)
 */
function isGlueyLine(line: string): boolean {
  return (
    LIST_LINE_RE.test(line) ||
    TABLE_LINE_RE.test(line) ||
    QUOTE_LINE_RE.test(line) ||
    CONTINUATION_LINE_RE.test(line)
  );
}

function countDoubleDollar(line: string): number {
  let count = 0;
  let idx = 0;
  while ((idx = line.indexOf("$$", idx)) !== -1) {
    count += 1;
    idx += 2;
  }
  return count;
}

export function emptyStreamBlocksState(): StreamBlocksState {
  return { chunks: [], continued: [], listAfter: [], settledText: "" };
}

/** Where the scan stands: inside a fence or `$$` math, and what the last lines allow. */
type ScanState = {
  fenceOpen: boolean;
  mathOpen: boolean;
  prevLineSafe: boolean;
  inBlankRun: boolean;
  list: OpenList | null;
  /**
   * BUG FIX: a closed rich block (fenced code, ```math, or $$ display math)
   * sitting in the pending segment used to wait for MIN_SETTLED_CHUNK_CHARS
   * like plain prose before it got cut into its own once-mounted chunk. A
   * short step-by-step math reply (each step's fence is well under 320
   * chars) could hold several ALREADY-CLOSED math blocks in that pending
   * segment for many streaming flushes in a row — and since the pending
   * segment re-parses from scratch on every flush (react-native-markdown-
   * display re-keys its whole output per parse, per this file's own header
   * comment), every KaTeX WebView inside it unmounted and remounted on every
   * flush: a real, repeated blank-then-repaint flicker, not settled prose's
   * merely-wasted re-parse cost. A rich block forces an eager cut at the
   * next safe boundary regardless of size, so it only ever renders once.
   */
  hasRichBlockSinceChunkStart: boolean;
};

/**
 * Track one line that a fence, `$$` math or a blank run accounts for, and
 * say so; a plain prose line (false) is where a cut may land.
 */
function trackBlockLine(state: ScanState, line: string): boolean {
  if (FENCE_LINE_RE.test(line)) {
    state.fenceOpen = !state.fenceOpen;
    state.prevLineSafe = !state.fenceOpen;
    state.inBlankRun = false;
    state.hasRichBlockSinceChunkStart = true;
    state.list = null;
    return true;
  }
  if (state.fenceOpen) {
    state.inBlankRun = false;
    return true;
  }

  const dollarCount = countDoubleDollar(line);
  if (dollarCount % 2 === 1) {
    state.mathOpen = !state.mathOpen;
    state.prevLineSafe = !state.mathOpen;
    state.inBlankRun = false;
    state.hasRichBlockSinceChunkStart = true;
    if (!CONTINUATION_LINE_RE.test(line)) state.list = null;
    return true;
  }
  if (state.mathOpen) {
    state.inBlankRun = false;
    return true;
  }
  if (dollarCount > 0) {
    // Even, nonzero count while not already inside an open block: one or
    // more complete, self-contained "$$...$$" spans on a single line (no
    // mathOpen state change) — an odd-count line above already covers the
    // multi-line open/close case; this covers the single-line one. Defer
    // to the next safe boundary like the fence/odd-count branches above
    // (instead of falling through to the cut-check below) so the cut
    // lands after this line, not at its start — the cut-check uses the
    // current line's start, so evaluating it on this same line would
    // slice the chunk right before the $$ content it's meant to include.
    state.prevLineSafe = true;
    state.inBlankRun = false;
    state.hasRichBlockSinceChunkStart = true;
    if (!CONTINUATION_LINE_RE.test(line)) state.list = null;
    return true;
  }

  if (isBlankLine(line)) {
    state.inBlankRun = true;
    return true;
  }
  return false;
}

type Cut = { at: number; continued: boolean; listAfter: OpenList | null };

/**
 * The cut points in `prepared` between `from` and `safeLen`, reading whole
 * lines only. A cut lands at the start of a prose line that follows a blank
 * run, when the line before the blank run may end a chunk and the line does
 * not glue to what came before; or before the next item of the open list.
 * Either needs the pending chunk to be long enough or to hold a closed rich
 * block. `from` is a chunk boundary, so every fence and `$$` block starts
 * closed, and `list` is the list open there.
 */
function scanClosedBlocks(
  prepared: string,
  from: number,
  safeLen: number,
  list: OpenList | null,
): Cut[] {
  const cuts: Cut[] = [];
  const state: ScanState = {
    fenceOpen: false,
    mathOpen: false,
    prevLineSafe: false,
    inBlankRun: false,
    list: list ? { ...list } : null,
    hasRichBlockSinceChunkStart: false,
  };
  let chunkStart = from;
  let i = from;
  while (i < safeLen) {
    const nl = prepared.indexOf("\n", i);
    if (nl === -1 || nl >= safeLen) break;
    const line = prepared.slice(i, nl);
    if (!trackBlockLine(state, line)) {
      const listBefore = state.list ? { ...state.list } : null;
      const nextItem = listItemCut(state, line);
      const longEnough =
        i - chunkStart >= MIN_SETTLED_CHUNK_CHARS || state.hasRichBlockSinceChunkStart;
      const afterBlock = state.inBlankRun && state.prevLineSafe && !isGlueyLine(line);
      if (longEnough && i > chunkStart && (afterBlock || nextItem)) {
        cuts.push({ at: i, continued: nextItem, listAfter: nextItem ? listBefore : null });
        chunkStart = i;
        state.hasRichBlockSinceChunkStart = false;
      }
      state.inBlankRun = false;
      state.prevLineSafe = true;
    }
    i = nl + 1;
  }
  return cuts;
}

/** Append the chunks between consecutive cuts to the settled state. */
function cutChunks(base: StreamBlocksState, prepared: string, cuts: Cut[]): StreamBlocksState {
  const chunks = base.chunks.slice();
  const continued = base.continued.slice();
  const listAfter = base.listAfter.slice();
  let settledText = base.settledText;
  let chunkStart = settledText.length;
  for (const cut of cuts) {
    const chunk = prepared.slice(chunkStart, cut.at);
    chunks.push(chunk);
    continued.push(cut.continued);
    // The list this chunk leaves open is the one the next chunk starts in.
    listAfter.push(cut.listAfter);
    settledText += chunk;
    chunkStart = cut.at;
  }
  return { chunks, continued, listAfter, settledText };
}

/**
 * The chunks of `state` that `prepared` still starts with: a preprocess pass
 * that rewrote earlier text, or a settled reply that differs from what
 * streamed, drops the chunks from there on, not all of them. A chunk drawn as
 * a list that goes on is kept only while the text after it still goes on with
 * that list.
 */
function keptPrefix(state: StreamBlocksState, prepared: string): StreamBlocksState {
  let keep = state.chunks.length;
  let length = state.settledText.length;
  if (!prepared.startsWith(state.settledText)) {
    keep = 0;
    length = 0;
    while (keep < state.chunks.length && prepared.startsWith(state.chunks[keep]!, length)) {
      length += state.chunks[keep]!.length;
      keep += 1;
    }
  }
  while (keep > 0 && state.continued[keep - 1] && !listGoesOn(state.listAfter[keep - 1]!, prepared, length)) {
    keep -= 1;
    length -= state.chunks[keep]!.length;
  }
  if (keep === state.chunks.length) return state;
  return {
    chunks: state.chunks.slice(0, keep),
    continued: state.continued.slice(0, keep),
    listAfter: state.listAfter.slice(0, keep),
    settledText: state.settledText.slice(0, length),
  };
}

/**
 * Advance the settled-chunk state for grown `prepared` content.
 *
 * `safeLen` bounds settling to the region whose preprocessing is final
 * (the prepared-stable prefix); the remainder stays in the live tail.
 * If `prepared` no longer extends the settled prefix (new stream, or a
 * preprocess pass rewrote earlier text) the chunks from the first one that
 * changed are dropped and cut again.
 */
export function advanceStreamBlocks(
  prev: StreamBlocksState | null,
  prepared: string,
  safeLen: number,
): StreamBlocksState {
  const base = keptPrefix(prev ?? emptyStreamBlocksState(), prepared);

  const boundedSafeLen = Math.min(Math.max(safeLen, 0), prepared.length);
  if (boundedSafeLen <= base.settledText.length) return base;

  const openList = base.listAfter[base.listAfter.length - 1] ?? null;
  const cuts = scanClosedBlocks(prepared, base.settledText.length, boundedSafeLen, openList);
  return cuts.length > 0 ? cutChunks(base, prepared, cuts) : base;
}
