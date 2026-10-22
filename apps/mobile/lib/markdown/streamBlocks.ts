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

import { fenceAfterLine, type OpenFence } from "@/lib/mdFenceScan";

export type StreamBlocksState = {
  /** Settled chunks; their concatenation is exactly `settledText`. */
  chunks: string[];
  /** Prefix of the prepared streaming text covered by `chunks`. */
  settledText: string;
};

/** Group small blocks together so long replies don't spawn hundreds of renderers. */
export const MIN_SETTLED_CHUNK_CHARS = 320;

const LIST_LINE_RE = /^ {0,3}(?:[-*+]|\d{1,9}[.)])(?:\s|$)/;
const TABLE_LINE_RE = /^ {0,3}\|/;
const QUOTE_LINE_RE = /^ {0,3}>/;
const CONTINUATION_LINE_RE = /^(?: {2,}|\t)/;

function isBlankLine(line: string): boolean {
  return line.trim().length === 0;
}

/**
 * Lines that glue to their neighbours across blank lines: cutting beside them
 * would restart ordered-list numbering, split tables/quotes, or detach list
 * continuations into a separate parse.
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
  return { chunks: [], settledText: "" };
}

/** Where the scan stands: inside a fence or `$$` math, and what the last lines allow. */
type ScanState = {
  /** Tracked open and closed, as `scanFences` reads fences: a ``` inside ~~~ is content. */
  openFence: OpenFence | null;
  mathOpen: boolean;
  prevLineSafe: boolean;
  inBlankRun: boolean;
  /**
   * A closed rich block (fenced code, ```math, or $$ display math) is cut into its
   * own once-mounted chunk at the next safe boundary, whatever its size, rather than
   * waiting for MIN_SETTLED_CHUNK_CHARS like prose. The pending segment re-parses on
   * every flush (react-native-markdown-display re-keys its output per parse, as this
   * file's header says), so a short step-by-step maths reply whose closed blocks waited
   * there would unmount and remount every KaTeX WebView on every flush: a blank-then-
   * repaint flicker.
   */
  hasRichBlockSinceChunkStart: boolean;
};

/**
 * Track one line that a fence, `$$` math or a blank run accounts for, and
 * say so; a plain prose line (false) is where a cut may land.
 */
function trackBlockLine(state: ScanState, line: string): boolean {
  const before = state.openFence;
  state.openFence = fenceAfterLine(before, line);
  if (before != null && state.openFence != null) {
    state.inBlankRun = false;
    return true;
  }
  if (before != null || state.openFence != null) {
    // The fence's opener or its closer.
    state.prevLineSafe = state.openFence == null;
    state.inBlankRun = false;
    state.hasRichBlockSinceChunkStart = true;
    return true;
  }

  const dollarCount = countDoubleDollar(line);
  if (dollarCount % 2 === 1) {
    state.mathOpen = !state.mathOpen;
    state.prevLineSafe = !state.mathOpen;
    state.inBlankRun = false;
    state.hasRichBlockSinceChunkStart = true;
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
    return true;
  }

  if (isBlankLine(line)) {
    state.inBlankRun = true;
    return true;
  }
  return false;
}

/**
 * The cut points in `prepared` between `from` and `safeLen`, reading whole
 * lines only. A cut lands at the start of a prose line that follows a blank
 * run, when the line before the blank run may end a chunk and neither side
 * glues to the other, once the pending chunk is long enough or holds a
 * closed rich block. `from` is a chunk boundary, so every fence and `$$`
 * block starts closed.
 */
function scanClosedBlocks(prepared: string, from: number, safeLen: number): number[] {
  const cuts: number[] = [];
  const state: ScanState = {
    openFence: null,
    mathOpen: false,
    prevLineSafe: false,
    inBlankRun: false,
    hasRichBlockSinceChunkStart: false,
  };
  let chunkStart = from;
  let i = from;
  while (i < safeLen) {
    const nl = prepared.indexOf("\n", i);
    if (nl === -1 || nl >= safeLen) break;
    const line = prepared.slice(i, nl);
    if (!trackBlockLine(state, line)) {
      const gluey = isGlueyLine(line);
      if (
        state.inBlankRun &&
        state.prevLineSafe &&
        !gluey &&
        (i - chunkStart >= MIN_SETTLED_CHUNK_CHARS || state.hasRichBlockSinceChunkStart)
      ) {
        cuts.push(i);
        chunkStart = i;
        state.hasRichBlockSinceChunkStart = false;
      }
      state.inBlankRun = false;
      state.prevLineSafe = !gluey;
    }
    i = nl + 1;
  }
  return cuts;
}

/** Append the chunks between consecutive cuts to the settled state. */
function cutChunks(base: StreamBlocksState, prepared: string, cuts: number[]): StreamBlocksState {
  const chunks = base.chunks.slice();
  let settledText = base.settledText;
  let chunkStart = settledText.length;
  for (const cut of cuts) {
    const chunk = prepared.slice(chunkStart, cut);
    chunks.push(chunk);
    settledText += chunk;
    chunkStart = cut;
  }
  return { chunks, settledText };
}

/**
 * Advance the settled-chunk state for grown `prepared` content.
 *
 * `safeLen` bounds settling to the region whose preprocessing is final
 * (the prepared-stable prefix); the remainder stays in the live tail.
 * If `prepared` no longer extends the settled prefix (new stream, or a
 * preprocess pass rewrote earlier text) the state resets and re-chunks.
 */
export function advanceStreamBlocks(
  prev: StreamBlocksState | null,
  prepared: string,
  safeLen: number,
): StreamBlocksState {
  let base = prev ?? emptyStreamBlocksState();
  if (!prepared.startsWith(base.settledText)) {
    base = emptyStreamBlocksState();
  }

  const boundedSafeLen = Math.min(Math.max(safeLen, 0), prepared.length);
  if (boundedSafeLen <= base.settledText.length) return base;

  const cuts = scanClosedBlocks(prepared, base.settledText.length, boundedSafeLen);
  return cuts.length > 0 ? cutChunks(base, prepared, cuts) : base;
}
