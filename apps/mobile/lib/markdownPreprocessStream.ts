import { preprocessMarkdown } from "@/lib/markdownPreprocess";

export type StreamingPreprocessCache = {
  /** Raw byte length covered by `preparedStable`. */
  rawStableLen: number;
  /** Preprocessed output for `content.slice(0, rawStableLen)`. */
  preparedStable: string;
  /**
   * Incremental-scan state for `preprocessMarkdownForStream`'s stability
   * check (see `scanStableMarkdownPrefix` below). Opaque to callers — just
   * round-trip it back in on the next call. `null` means "start a fresh
   * scan" (e.g. a new stream, or a cache that predates this field).
   */
  scanState: StableScanState | null;
};

/**
 * Longest raw prefix safe to preprocess while the message is still growing.
 * Excludes partial lines and regions inside unclosed fences / block math.
 *
 * This is the simple, non-incremental reference implementation: it re-scans
 * from the start of `content` on every call. It is kept exactly as it was
 * (and is still covered directly by tests) as the ground truth that
 * `scanStableMarkdownPrefix`'s incremental fast path is checked against.
 *
 * The streaming hot path (`preprocessMarkdownForStream`) does NOT call this
 * function — it uses the incremental scanner instead, because re-running a
 * whole-prefix scan from scratch on every ~48ms throttle tick is
 * O(content length) per call, and while a single fence/math block/callout
 * stays open across many ticks, that cost is paid again and again as the
 * unstable region grows (cost grows with how long the structure stays open).
 */
export function findStableMarkdownPrefixLen(content: string): number {
  if (!content) return 0;

  let end = content.length;
  if (!content.endsWith("\n")) {
    const lastNl = content.lastIndexOf("\n");
    if (lastNl === -1) return 0;
    end = lastNl + 1;
  }

  while (end > 0) {
    const prefix = content.slice(0, end);
    if (!hasUnclosedStreamingStructure(prefix)) return end;
    const prevNl = prefix.lastIndexOf("\n", prefix.length - 2);
    if (prevNl === -1) return 0;
    end = prevNl + 1;
  }

  return 0;
}

function hasUnclosedStreamingStructure(text: string): boolean {
  if (countOccurrences(text, "$$") % 2 !== 0) return true;
  if (countFenceMarkers(text) % 2 !== 0) return true;
  // \[...\] is the other block-math delimiter preprocessMarkdown converts
  // (BLOCK_MATH_BRACKET_RE, alongside $$...$$) — without tracking it here
  // too, an unclosed \[ mid-stream gets folded into the "stable" prefix and
  // preprocessed while still open, leaving a raw dangling "\[" visible until
  // the closing \] finally arrives.
  if (countOccurrences(text, "\\[") !== countOccurrences(text, "\\]")) return true;
  if (endsWithOpenCallout(text)) return true;
  return false;
}

/** True when `text` ends inside an open GFM callout (line-scan, no ReDoS). */
function endsWithOpenCallout(text: string): boolean {
  const lines = text.split("\n");
  // A trailing `\n` leaves an empty final segment — skip it.
  let i = lines.length - 1;
  if (i >= 0 && lines[i] === "") i -= 1;
  // Walk back over trailing quote-continuation lines to a `> [!type]` marker.
  // Marker must not be the absolute first line of the message (needs a prior `\n`).
  while (i >= 0 && /^>\s?/.test(lines[i])) {
    if (i > 0 && /^>\s*\[!\w+\]/i.test(lines[i])) return true;
    i -= 1;
  }
  return false;
}

function countFenceMarkers(text: string): number {
  // Count both ``` and ~~~ fence markers — markdown treats them as
  // equivalent fence delimiters, so a ~~~-opened fence must contribute to
  // the parity check or the reference scan would report an unclosed fence
  // as "stable" (and vice versa).
  const backtick = text.match(/^```/gm);
  const tilde = text.match(/^~~~/gm);
  return (backtick?.length ?? 0) + (tilde?.length ?? 0);
}

function countOccurrences(text: string, needle: string): number {
  if (!needle) return 0;
  let count = 0;
  let idx = 0;
  while ((idx = text.indexOf(needle, idx)) !== -1) {
    count += 1;
    idx += needle.length;
  }
  return count;
}

const CALLOUT_MARKER_LINE_RE = /^>\s*\[!\w+\]/i;

export type StableScanState = {
  /** Absolute offset into `content` already folded into the fields below. */
  scannedLen: number;
  /** Parity of ``` fence-marker lines seen so far (true = inside a fence). */
  fenceOpen: boolean;
  /** Parity of `$$` occurrences seen so far (true = inside block math). */
  dollarOpen: boolean;
  /** Running count of `\[` minus `\]` seen so far (nonzero = inside \[...\] block math). */
  bracketDepth: number;
  /** Whether an unclosed `> [!type]` callout chain reaches `scannedLen`. */
  calloutOpen: boolean;
  /** Largest confirmed-stable prefix length found up to `scannedLen`. */
  stableEnd: number;
};

/**
 * Incremental equivalent of `findStableMarkdownPrefixLen`, used by the
 * streaming hot path.
 *
 * `findStableMarkdownPrefixLen` finds the answer by walking backward from
 * the end of `content` line by line, re-running a whole-prefix regex/count
 * scan (`hasUnclosedStreamingStructure`) at every candidate boundary. For a
 * reply that opens one giant code fence and keeps streaming for thousands of
 * characters before closing it, every candidate boundary inside that fence
 * is unstable, so the walk visits — and fully re-scans from position 0 —
 * every line of the fence, every tick, for as long as it stays open.
 *
 * This function instead scans `content` forward line by line exactly once,
 * maintaining running parity/state for fences, `$$` math, and callouts as it
 * goes (folding in each line is O(1)), and remembers the last line boundary
 * where all three were "closed". Given a previous call's returned state, a
 * later call for grown (append-only) `content` resumes from
 * `state.scannedLen` instead of re-scanning from position 0 — so the work
 * done on each call is bounded by how much *new* text arrived since the
 * previous call, not by how much of the message is still open.
 *
 * Why resuming is safe: `scannedLen` is always a full-line boundary (0 or
 * right after a `\n`), and the fence/`$$` parity + callout state cached at
 * that boundary are exactly the running state a whole-prefix scan of
 * `content.slice(0, scannedLen)` would have computed. Appending more text
 * cannot retroactively change whether that earlier text closed its
 * fences/math/callouts (its own parity/chain state is a closed fact once
 * written), so the cached state stays valid — only the newly appended lines
 * need to be folded in. (This mirrors why `findStableMarkdownPrefixLen`'s
 * own answer never needs to re-examine text before a boundary it already
 * proved stable: a stable prefix's internal balance can't be undone by
 * appending after it.)
 *
 * If `prevState` looks stale (its `scannedLen` is past the current content —
 * should not happen for append-only streaming content, but checked
 * defensively), the scan restarts from 0.
 */
function scanStableMarkdownPrefix(
  content: string,
  prevState: StableScanState | null,
): StableScanState {
  let end0 = content.length;
  if (!content.endsWith("\n")) {
    const lastNl = content.lastIndexOf("\n");
    end0 = lastNl === -1 ? 0 : lastNl + 1;
  }

  let fenceOpen = false;
  let dollarOpen = false;
  let bracketDepth = 0;
  let calloutOpen = false;
  let stableEnd = 0;
  let pos = 0;

  if (prevState && prevState.scannedLen <= end0) {
    pos = prevState.scannedLen;
    fenceOpen = prevState.fenceOpen;
    dollarOpen = prevState.dollarOpen;
    bracketDepth = prevState.bracketDepth;
    calloutOpen = prevState.calloutOpen;
    stableEnd = prevState.stableEnd;
  }

  while (pos < end0) {
    const nl = content.indexOf("\n", pos);
    if (nl === -1 || nl >= end0) break;
    const line = content.slice(pos, nl);
    const isAbsoluteFirstLine = pos === 0;

    // Toggle fence state for both ``` and ~~~ delimiters — markdown treats
    // them as equivalent fence markers, so a ~~~-opened fence must keep the
    // scanner from treating its body as stable (otherwise the streaming
    // preprocessor would cut mid-fence and render a half-open fence).
    if (line.startsWith("```") || line.startsWith("~~~")) fenceOpen = !fenceOpen;
    if (countOccurrences(line, "$$") % 2 !== 0) dollarOpen = !dollarOpen;
    bracketDepth += countOccurrences(line, "\\[") - countOccurrences(line, "\\]");
    // A callout chain continues as long as each new line still starts with
    // ">" (matching the original regex's permissive continuation pattern);
    // otherwise it only (re)starts on a proper `> [!type]` marker line — and
    // per the original regex, a marker line at the absolute start of the
    // whole message (no preceding "\n" before it) never counts, so that's
    // excluded here too.
    calloutOpen = calloutOpen
      ? line.startsWith(">")
      : !isAbsoluteFirstLine && CALLOUT_MARKER_LINE_RE.test(line);

    pos = nl + 1;
    if (!fenceOpen && !dollarOpen && bracketDepth === 0 && !calloutOpen) {
      stableEnd = pos;
    }
  }

  return { scannedLen: end0, fenceOpen, dollarOpen, bracketDepth, calloutOpen, stableEnd };
}

/**
 * Incrementally preprocess append-only streaming markdown.
 * Stable prefix is fully preprocessed; the trailing unstable region stays raw
 * until it closes (or the stream ends and a full preprocess runs).
 */
export function preprocessMarkdownForStream(
  content: string,
  cache: StreamingPreprocessCache | null,
): { prepared: string; cache: StreamingPreprocessCache } {
  const scanState = scanStableMarkdownPrefix(content, cache?.scanState ?? null);
  const stableLen = scanState.stableEnd;

  if (stableLen === 0) {
    return {
      prepared: content,
      cache: { rawStableLen: 0, preparedStable: "", scanState },
    };
  }

  if (stableLen === content.length) {
    const prepared = preprocessMarkdown(content);
    return {
      prepared,
      cache: { rawStableLen: stableLen, preparedStable: prepared, scanState },
    };
  }

  const stableRaw = content.slice(0, stableLen);
  let preparedStable = cache?.preparedStable ?? "";
  if (
    !cache ||
    cache.rawStableLen !== stableLen ||
    content.slice(0, cache.rawStableLen) !== stableRaw
  ) {
    preparedStable = preprocessMarkdown(stableRaw);
  }

  const tail = content.slice(stableLen);
  return {
    prepared: preparedStable + tail,
    cache: { rawStableLen: stableLen, preparedStable, scanState },
  };
}
