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
const FENCE_LINE_RE = /^(?:```|~~~)/;

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

  const chunks = base.chunks.slice();
  let settledText = base.settledText;
  let chunkStart = settledText.length;
  // Cut points always land where fences/math are closed, so scanning from a
  // chunk boundary starts in the closed state.
  let fenceOpen = false;
  let mathOpen = false;
  let prevLineSafe = false;
  let inBlankRun = false;
  let didCut = false;

  let i = chunkStart;
  while (i < boundedSafeLen) {
    const nl = prepared.indexOf("\n", i);
    if (nl === -1 || nl >= boundedSafeLen) break;
    const line = prepared.slice(i, nl);
    const lineEnd = nl + 1;

    if (FENCE_LINE_RE.test(line)) {
      fenceOpen = !fenceOpen;
      prevLineSafe = !fenceOpen;
      inBlankRun = false;
      i = lineEnd;
      continue;
    }
    if (fenceOpen) {
      inBlankRun = false;
      i = lineEnd;
      continue;
    }

    if (countDoubleDollar(line) % 2 === 1) {
      mathOpen = !mathOpen;
      prevLineSafe = !mathOpen;
      inBlankRun = false;
      i = lineEnd;
      continue;
    }
    if (mathOpen) {
      inBlankRun = false;
      i = lineEnd;
      continue;
    }

    if (isBlankLine(line)) {
      inBlankRun = true;
      i = lineEnd;
      continue;
    }

    const gluey = isGlueyLine(line);
    if (
      inBlankRun &&
      prevLineSafe &&
      !gluey &&
      i - chunkStart >= MIN_SETTLED_CHUNK_CHARS
    ) {
      const chunk = prepared.slice(chunkStart, i);
      chunks.push(chunk);
      settledText += chunk;
      chunkStart = i;
      didCut = true;
    }
    inBlankRun = false;
    prevLineSafe = !gluey;
    i = lineEnd;
  }

  return didCut ? { chunks, settledText } : base;
}
