import { preprocessMarkdown, type PreprocessOptions } from "@/lib/markdown/preprocess";
import { presentStreamTail } from "@/lib/markdown/presentation";
import {
  advanceSegmentedPrefix,
  finishSegmentedPrefix,
  type SegmentedPrefix,
} from "@/lib/markdown/segmentedPreprocess";
import { dollarDisplayOpenAfter } from "@/lib/markdown/displayDollars";
import { pairLazily } from "@/lib/markdown/streamSegments";
import { isWorkedReply } from "@/lib/markdown/workoutSection";
import { fenceAfterLine, type OpenFence } from "@/lib/fence/scan";

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
  /** `preparedStable` was prepared as server-presented text (PreprocessOptions). */
  presented: boolean;
  /** The stable prefix in parts, each preprocessed once (segmentedPreprocess.ts). */
  segments?: SegmentedPrefix | null;
  /** The maths formatter `segments` were preprocessed with. */
  mathFormat?: (expr: string) => string;
  /** `isWorkedReply` of the open part, read once while it stays the same. */
  openWorked?: { raw: string; worked: boolean };
};

/**
 * Longest raw prefix safe to preprocess while the message is still growing.
 * Excludes partial lines and regions inside unclosed fences / block math.
 *
 * This is the simple, non-incremental reference implementation: it re-scans
 * from the start of `content` on every call, and the tests check
 * `scanStableMarkdownPrefix`'s incremental fast path against it. Both read a
 * line's maths delimiters with `lineMathMarkers`, so that cross-check covers
 * the incremental bookkeeping, not the delimiter rule; the rule itself is
 * pinned by expected values in `markdownPreprocessStream.test.ts`.
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

/** `$`, `$$`, `\[`, and `\(` inside a code fence are code, not math. */
function mathMarkersOutsideFences(text: string): {
  dollarOpen: boolean;
  bracketOpen: boolean;
  parenOpen: boolean;
  fenceOpen: boolean;
} {
  let openFence: OpenFence | null = null;
  let dollarOpen = false;
  let bracketOpen = false;
  let parenOpen = false;
  let pos = 0;
  while (pos < text.length) {
    const nl = text.indexOf("\n", pos);
    const lineEnd = nl === -1 ? text.length : nl;
    const line = text.slice(pos, lineEnd);
    const before = openFence;
    openFence = fenceAfterLine(openFence, line);
    if (before == null && openFence == null) {
      const markers = lineMathMarkers(line, dollarOpen, bracketOpen, parenOpen);
      dollarOpen = markers.dollarOpen;
      bracketOpen = markers.bracketOpen;
      parenOpen = markers.parenOpen;
    }
    if (nl === -1) break;
    pos = nl + 1;
  }
  return { dollarOpen, bracketOpen, parenOpen, fenceOpen: openFence != null };
}

function hasUnclosedStreamingStructure(text: string): boolean {
  const math = mathMarkersOutsideFences(text);
  if (math.dollarOpen) return true;
  // A single `$` holds nothing: only whole lines are stable, and a `$` span never
  // reaches past its line (`readInlineMathSpan`), so a closed line's odd `$`
  // ("a $300 deposit", a price list) can never close later.
  if (math.fenceOpen) return true;
  // \[...\] is the other block-math delimiter preprocessMarkdown converts
  // (BLOCK_MATH_BRACKET_RE, alongside $$...$$) — without tracking it here
  // too, an unclosed \[ mid-stream gets folded into the "stable" prefix and
  // preprocessed while still open, leaving a raw dangling "\[" visible until
  // the closing \] finally arrives.
  if (math.bracketOpen) return true;
  // \(...\) inline math, which may span lines.
  if (math.parenOpen) return true;
  if (endsWithOpenCallout(text)) return true;
  if (endsWithOpenPipeTable(text)) return true;
  return false;
}

/**
 * The maths delimiters of one line outside a fence. `$$`, `\[…\]` and
 * `\(…\)` may span lines, so they carry across them. `$$` is read as
 * `convertBlockMath` reads it (`displayDollars.ts`: code, escapes and price
 * tiers hold none). `\[` and `\(` pair lazily, as the preprocess regexes read
 * them (`/\\\[([\s\S]+?)\\\]/`): an opener waits for the next closer, and a
 * closer with no opener is not one. A single `$` pairs only on its line, so
 * it is not read here.
 */
function lineMathMarkers(
  line: string,
  dollarOpen: boolean,
  bracketOpen: boolean,
  parenOpen: boolean,
): { dollarOpen: boolean; bracketOpen: boolean; parenOpen: boolean } {
  if (!line.includes("$") && !line.includes("\\") && !(dollarOpen && line.trim())) {
    return { dollarOpen, bracketOpen, parenOpen };
  }
  return {
    dollarOpen: dollarDisplayOpenAfter(line, dollarOpen),
    bracketOpen: pairLazily(line, bracketOpen, "\\[", "\\]"),
    parenOpen: pairLazily(line, parenOpen, "\\(", "\\)"),
  };
}

/** True when the last complete line is a GFM pipe-table row (still growing). */
function endsWithOpenPipeTable(text: string): boolean {
  const lines = text.split("\n");
  let i = lines.length - 1;
  if (i >= 0 && lines[i] === "") i -= 1;
  if (i < 0) return false;
  return looksLikePipeTableLine(lines[i] ?? "");
}

function looksLikePipeTableLine(line: string): boolean {
  const trimmed = line.trim();
  if (!trimmed.startsWith("|")) return false;
  return trimmed.indexOf("|", 1) >= 0;
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

const CALLOUT_MARKER_LINE_RE = /^>\s*\[!\w+\]/i;

type StableScanState = {
  /** Absolute offset into `content` already folded into the fields below. */
  scannedLen: number;
  /**
   * The fence open at `scannedLen`, tracked open and closed (not a parity count of fence
   * lines): a ``` line inside a ~~~ block is that block's content (audit DUP-03).
   */
  openFence: OpenFence | null;
  /** Parity of `$$` occurrences seen so far (true = inside block math). */
  dollarOpen: boolean;
  /** 1 inside \[...\] block math, paired lazily (`lineMathMarkers`), else 0. */
  bracketDepth: number;
  /** 1 inside \(...\) inline math, which may span lines, paired lazily, else 0. */
  parenDepth: number;
  /** Whether an unclosed `> [!type]` callout chain reaches `scannedLen`. */
  calloutOpen: boolean;
  /** Whether an unclosed GFM pipe-table chain reaches `scannedLen`. */
  pipeTableOpen: boolean;
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

  let openFence: OpenFence | null = null;
  let dollarOpen = false;
  let bracketDepth = 0;
  let parenDepth = 0;
  let calloutOpen = false;
  let pipeTableOpen = false;
  let stableEnd = 0;
  let pos = 0;

  if (prevState && prevState.scannedLen <= end0) {
    pos = prevState.scannedLen;
    openFence = prevState.openFence ?? null;
    dollarOpen = prevState.dollarOpen;
    bracketDepth = prevState.bracketDepth;
    parenDepth = prevState.parenDepth;
    calloutOpen = prevState.calloutOpen;
    pipeTableOpen = prevState.pipeTableOpen;
    stableEnd = prevState.stableEnd;
  }

  while (pos < end0) {
    const nl = content.indexOf("\n", pos);
    if (nl === -1 || nl >= end0) break;
    const line = content.slice(pos, nl);
    const isAbsoluteFirstLine = pos === 0;

    // ``` and ~~~ fences both keep their body unstable (otherwise the streaming
    // preprocessor would cut mid-fence and render a half-open fence).
    const before = openFence;
    openFence = fenceAfterLine(openFence, line);
    // A single `$` pairs only on its line (`readInlineMathSpan`), so it holds no
    // whole line: "a $300 deposit" or a price list settles as it comes.
    if (before == null && openFence == null) {
      const markers = lineMathMarkers(line, dollarOpen, bracketDepth !== 0, parenDepth !== 0);
      dollarOpen = markers.dollarOpen;
      bracketDepth = markers.bracketOpen ? 1 : 0;
      parenDepth = markers.parenOpen ? 1 : 0;
    }
    // A callout chain continues as long as each new line still starts with
    // ">" (matching the original regex's permissive continuation pattern);
    // otherwise it only (re)starts on a proper `> [!type]` marker line — and
    // per the original regex, a marker line at the absolute start of the
    // whole message (no preceding "\n" before it) never counts, so that's
    // excluded here too.
    calloutOpen = calloutOpen
      ? line.startsWith(">")
      : !isAbsoluteFirstLine && CALLOUT_MARKER_LINE_RE.test(line);
    pipeTableOpen = looksLikePipeTableLine(line);

    pos = nl + 1;
    if (
      openFence == null &&
      !dollarOpen &&
      bracketDepth === 0 &&
      parenDepth === 0 &&
      !calloutOpen &&
      !pipeTableOpen
    ) {
      stableEnd = pos;
    }
  }

  return {
    scannedLen: end0,
    openFence,
    dollarOpen,
    bracketDepth,
    parenDepth,
    calloutOpen,
    pipeTableOpen,
    stableEnd,
  };
}

/**
 * Incrementally preprocess append-only streaming markdown.
 * The stable prefix is preprocessed exactly as `preprocessMarkdown` would the
 * whole of it, in parts that each run once (segmentedPreprocess.ts), so a
 * flush costs the new text rather than the reply. The trailing unstable region
 * stays raw until it closes (or the stream ends and a full preprocess runs).
 * The text still streaming is the model's own and is presented here;
 * `presented` text is a saved row held in stream layout while it settles.
 */
export function preprocessMarkdownForStream(
  content: string,
  cache: StreamingPreprocessCache | null,
  mathFormat?: (expr: string) => string,
  options: PreprocessOptions = {},
): { prepared: string; cache: StreamingPreprocessCache } {
  const presented = options.presented === true;
  const scanState = scanStableMarkdownPrefix(content, cache?.scanState ?? null);
  const stableLen = scanState.stableEnd;

  if (stableLen === 0) {
    return {
      prepared: presentStreamTail(content, presented),
      cache: { rawStableLen: 0, preparedStable: "", scanState, presented },
    };
  }

  const reusable = cache && cache.presented === presented && cache.mathFormat === mathFormat;
  const { prefix, preparedStable } = advanceSegmentedPrefix(
    reusable ? (cache.segments ?? null) : null,
    content,
    stableLen,
    (raw, workedAbove) => preprocessMarkdown(raw, mathFormat, { ...options, workedAbove }),
  );
  const tail = content.slice(stableLen);
  // A heading in the tail of a worked reply starts its own paragraph (`separateLeadLines`),
  // the tail's first line too: its line above is the closed text's last (b12, 2026-11-13).
  const openWorked =
    cache?.openWorked && cache.openWorked.raw === prefix.openRaw
      ? cache.openWorked
      : { raw: prefix.openRaw, worked: isWorkedReply(prefix.openRaw) };
  const workedAbove = prefix.workedAbove || openWorked.worked;
  // The closed text's last line: from the newline before it (or the start) to its own.
  const above = content.slice(content.lastIndexOf("\n", stableLen - 2) + 1, stableLen - 1);
  return {
    prepared: preparedStable + presentStreamTail(tail, presented, workedAbove, above),
    cache: {
      rawStableLen: stableLen,
      preparedStable,
      scanState,
      presented,
      segments: prefix,
      mathFormat,
      openWorked,
    },
  };
}

/**
 * A reply that has just finished streaming, preprocessed as
 * `preprocessMarkdown` preprocesses it whole. The parts its stream already
 * preprocessed (`cache`) are kept, so the end of a long reply preprocesses the
 * text after its last cut, not the whole reply again. A reply that changed
 * before that cut, or a cache made with other options, is preprocessed whole.
 */
export function preprocessSettledMarkdown(
  content: string,
  cache: StreamingPreprocessCache | null,
  mathFormat?: (expr: string) => string,
  options: PreprocessOptions = {},
): string {
  const preprocess = (raw: string, workedAbove = false) =>
    preprocessMarkdown(raw, mathFormat, { ...options, workedAbove });
  const segments =
    cache && cache.presented === (options.presented === true) && cache.mathFormat === mathFormat
      ? cache.segments
      : null;
  if (segments) return finishSegmentedPrefix(segments, content, preprocess) ?? preprocess(content);
  if (options.workedAbove !== undefined) return preprocess(content);
  return rememberedWhole(content, mathFormat, options.presented === true, () => preprocess(content));
}

/**
 * The last few settled replies preprocessed whole, by text, formatter and
 * presentation. A list row mounts again each time it scrolls back into view,
 * and `preprocessMarkdown` is a pure function of these three.
 */
const WHOLE_MEMO_SIZE = 24;
const wholeMemo = new Map<string, string>();

/** Sign-out: the replies remembered were the account's. */
export function clearSettledMarkdownMemo(): void {
  wholeMemo.clear();
}
const formatterIds = new WeakMap<(expr: string) => string, number>();
let nextFormatterId = 1;

function rememberedWhole(
  content: string,
  mathFormat: ((expr: string) => string) | undefined,
  presented: boolean,
  make: () => string,
): string {
  let formatter = 0;
  if (mathFormat) {
    formatter = formatterIds.get(mathFormat) ?? 0;
    if (!formatter) {
      formatter = nextFormatterId++;
      formatterIds.set(mathFormat, formatter);
    }
  }
  const key = `${formatter}:${presented ? 1 : 0}:${content}`;
  const known = wholeMemo.get(key);
  if (known !== undefined) {
    // Most recently used last, so the oldest goes first.
    wholeMemo.delete(key);
    wholeMemo.set(key, known);
    return known;
  }
  const made = make();
  wholeMemo.set(key, made);
  if (wholeMemo.size > WHOLE_MEMO_SIZE) wholeMemo.delete(wholeMemo.keys().next().value!);
  return made;
}
