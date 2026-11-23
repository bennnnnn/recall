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
 * Chunks append while the same reply streams, and a chunk's string does not
 * change, so its parse/render is done once. The exceptions: a preprocess pass
 * that rewrote earlier text, a list that went wide, and a link reference,
 * which may merge settled chunks or take them back (`streamReferences.ts`).
 */

import { listGoesOn, type OpenList } from "@/lib/markdown/streamListCuts";
import {
  MIN_SETTLED_CHUNK_CHARS,
  scanClosedBlocks,
  type Cut,
} from "@/lib/markdown/streamBlockScan";
import { NO_REFS, pieceRefs, tiedSpan, type PieceRefs } from "@/lib/markdown/streamReferences";

export type { OpenList } from "@/lib/markdown/streamListCuts";
export { MIN_SETTLED_CHUNK_CHARS };

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
  /**
   * Per chunk: the link reference labels it defines and uses. A reference
   * resolves only in the piece its definition is in, so the pieces from the
   * first that uses or defines a label to the last are one (`streamReferences.ts`).
   */
  refs: PieceRefs[];
};

export function emptyStreamBlocksState(): StreamBlocksState {
  return { chunks: [], continued: [], listAfter: [], settledText: "", refs: [] };
}

/** Append the chunks between consecutive cuts to the settled state. */
function cutChunks(base: StreamBlocksState, prepared: string, cuts: Cut[]): StreamBlocksState {
  const chunks = base.chunks.slice();
  const continued = base.continued.slice();
  const listAfter = base.listAfter.slice();
  const refs = base.refs.slice();
  let settledText = base.settledText;
  let chunkStart = settledText.length;
  for (const cut of cuts) {
    const chunk = prepared.slice(chunkStart, cut.at);
    chunks.push(chunk);
    continued.push(cut.continued);
    // The list this chunk leaves open is the one the next chunk starts in.
    listAfter.push(cut.listAfter);
    refs.push(pieceRefs(chunk));
    settledText += chunk;
    chunkStart = cut.at;
  }
  return { chunks, continued, listAfter, settledText, refs };
}

/**
 * `state` with the pieces a link reference ties drawn as one: the chunks
 * from the first tied one to the last are merged, or, when the text after
 * the chunks is tied too, left to it.
 */
function tieReferences(state: StreamBlocksState, prepared: string): StreamBlocksState {
  const from = state.settledText.length;
  // No definition anywhere: nothing to tie (the common reply skips the live text's read).
  if (!prepared.includes("]:", from) && state.refs.every((refs) => refs.defines.length === 0)) return state;
  const live = pieceRefs(prepared.slice(from));
  const span = tiedSpan([...state.refs, live]);
  if (!span) return state;
  if (span.last === state.chunks.length) return trimmedTo(state, span.first);
  if (span.last === span.first) return state;
  return mergedChunks(state, span.first, span.last);
}

/** `state` with its chunks `first` to `last` joined into one. */
function mergedChunks(state: StreamBlocksState, first: number, last: number): StreamBlocksState {
  const joined = state.refs.slice(first, last + 1);
  const refs: PieceRefs = {
    defines: [...new Set(joined.flatMap((r) => r.defines))],
    mentions: [...new Set(joined.flatMap((r) => r.mentions))],
  };
  const splice = <T,>(list: T[], value: T) => [...list.slice(0, first), value, ...list.slice(last + 1)];
  return {
    chunks: splice(state.chunks, state.chunks.slice(first, last + 1).join("")),
    continued: splice(state.continued, state.continued[last]!),
    listAfter: splice(state.listAfter, state.listAfter[last] ?? null),
    settledText: state.settledText,
    refs: splice(state.refs, refs.defines.length || refs.mentions.length ? refs : NO_REFS),
  };
}

/** `state` without its last chunks that end inside a list: the list is cut again whole. */
function withoutOpenListChunks(state: StreamBlocksState): StreamBlocksState {
  let keep = state.chunks.length;
  while (keep > 0 && state.continued[keep - 1]) keep -= 1;
  return trimmedTo(state, keep);
}

function trimmedTo(state: StreamBlocksState, keep: number): StreamBlocksState {
  if (keep === state.chunks.length) return state;
  const length = state.chunks.slice(0, keep).reduce((sum, chunk) => sum + chunk.length, 0);
  return {
    chunks: state.chunks.slice(0, keep),
    continued: state.continued.slice(0, keep),
    listAfter: state.listAfter.slice(0, keep),
    settledText: state.settledText.slice(0, length),
    refs: state.refs.slice(0, keep),
  };
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
  return trimmedTo(state, keep);
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
  let base = keptPrefix(prev ?? emptyStreamBlocksState(), prepared);

  // Cut only in the closed text; read the live end too (see scanClosedBlocks).
  const boundedSafeLen = Math.min(Math.max(safeLen, 0), prepared.length);
  const scanFrom = (state: StreamBlocksState) =>
    scanClosedBlocks(
      prepared,
      state.settledText.length,
      Math.max(boundedSafeLen, state.settledText.length),
      lastOpenList(state),
      prepared.length,
    );
  let scan = scanFrom(base);
  if (scan.inheritedWide) {
    base = withoutOpenListChunks(base);
    scan = scanFrom(base);
  }
  const cut = scan.cuts.length > 0 ? cutChunks(base, prepared, scan.cuts) : base;
  return tieReferences(cut, prepared);
}

/**
 * The chunks a settled reply is drawn with: those of its stream it still
 * starts with, the rest in one piece, so what was drawn is not drawn again.
 * No new cuts. The pieces a link reference ties are one, and a numbered list
 * that reached 100 is drawn whole.
 */
export function settleStreamBlocks(
  prev: StreamBlocksState | null,
  prepared: string,
): StreamBlocksState {
  let base = keptPrefix(prev ?? emptyStreamBlocksState(), prepared);
  if (base.chunks.length === 0) return base;
  const scanFrom = (state: StreamBlocksState) => {
    const settledEnd = state.settledText.length;
    return scanClosedBlocks(prepared, settledEnd, settledEnd, lastOpenList(state), prepared.length);
  };
  let scan = scanFrom(base);
  if (scan.inheritedWide) {
    base = withoutOpenListChunks(base);
    scan = scanFrom(base);
  }
  return tieReferences(base, prepared);
}

function lastOpenList(state: StreamBlocksState): OpenList | null {
  return state.listAfter[state.listAfter.length - 1] ?? null;
}
