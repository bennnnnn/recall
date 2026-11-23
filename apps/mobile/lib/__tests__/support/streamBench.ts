/**
 * The streaming pipeline a reply's row runs on every flush, without React:
 * the row's content model (`deriveAssistantMessageContent`, emoji placement),
 * then what `MarkdownContent` does (preview scan, stream preprocess, settled
 * chunks, the live end) and markdown-it on every piece that changed. Used by
 * the flush benchmark and the "streams the same as it settles" test.
 */
import type { MarkdownProps } from "@/components/markdown/MarkdownPiece";
import { makeRenderRules } from "@/components/markdown/markdownRenderRules";
import { streamingEnd } from "@/components/markdown/streamingEnd";
import { placeLiveEmoji } from "@/features/chat/model/emojiPlacement";
import { deriveAssistantMessageContent } from "@/lib/markdown/assistantMessageContent";
import { markdownItInstance } from "@/lib/markdown/parser";
import {
  preprocessMarkdownForStream,
  preprocessSettledMarkdown,
  type StreamingPreprocessCache,
} from "@/lib/markdown/preprocessStream";
import { advanceStreamBlocks, type StreamBlocksState } from "@/lib/markdown/streamBlocks";
import { advancePreviewFilesScan, type PreviewScanState } from "@/lib/preview/htmlPreviewBundle";
import { lightTheme } from "@/lib/theme";

const { rules, mdStyles } = makeRenderRules(lightTheme);
const MD: MarkdownProps = { style: mdStyles, rules, markdownit: markdownItInstance };

export type FlushStats = {
  flushes: number;
  ms: number;
  /** Characters markdown-it parsed: every new chunk once, the live piece every flush. */
  parsedChars: number;
  /** The raw text held out of the stable prefix, summed over flushes. */
  unstableChars: number;
  /** Settled chunks when the stream ended. */
  chunks: number;
  /** Of `ms`, the row's content model (fences stripped, emoji placed). */
  rowMs: number;
  /** Of `ms`, markdown-it. */
  parseMs: number;
  /** Flushes that dropped settled chunks (their text changed, or a rule took them back). */
  chunkDrops: number;
};

export type StreamRun = {
  stats: FlushStats;
  /** The prepared text once the reply settled. */
  settled: string;
};

export function rowMarkdown(content: string, generating: boolean): string {
  const live = placeLiveEmoji(content, "some", null) ?? "";
  return deriveAssistantMessageContent({
    content: live,
    layoutFrozen: false,
    isUser: false,
    priorUserText: null,
    messageId: "bench",
    isGenerating: generating,
  }).markdownContent;
}

/** Stream `reply` in `step`-character flushes through the row's pipeline, then settle it. */
export function streamReply(
  reply: string,
  step = 30,
  mathFormat?: (expr: string) => string,
): StreamRun {
  let pre: StreamingPreprocessCache | null = null;
  let blocks: StreamBlocksState | null = null;
  let preview: PreviewScanState | null = null;
  const stats: FlushStats = { flushes: 0, ms: 0, parsedChars: 0, unstableChars: 0, chunks: 0, chunkDrops: 0, rowMs: 0, parseMs: 0 };
  const started = performance.now();
  for (let end = Math.min(step, reply.length); ; end = Math.min(end + step, reply.length)) {
    const rowStart = performance.now();
    const content = rowMarkdown(reply.slice(0, end), true);
    stats.rowMs += performance.now() - rowStart;
    preview = advancePreviewFilesScan(preview, content);
    const result = preprocessMarkdownForStream(content, pre, mathFormat);
    pre = result.cache;
    const before = blocks?.chunks ?? [];
    blocks = advanceStreamBlocks(blocks, result.prepared, pre.preparedStable.length);
    if (blocks.chunks.length < before.length) stats.chunkDrops += 1;
    const tail = streamingEnd(result.prepared, blocks.settledText.length, pre, MD);
    const parseStart = performance.now();
    // A piece whose text is the same as last flush's is not parsed again (MarkdownPiece is memoized).
    blocks.chunks.forEach((chunk, index) => {
      if (chunk === before[index]) return;
      markdownItInstance.parse(chunk, {});
      stats.parsedChars += chunk.length;
    });
    markdownItInstance.parse(tail.live, {});
    stats.parsedChars += tail.live.length;
    stats.parseMs += performance.now() - parseStart;
    stats.unstableChars += content.length - pre.rawStableLen;
    stats.flushes += 1;
    if (end >= reply.length) break;
  }
  stats.ms = performance.now() - started;
  stats.chunks = blocks?.chunks.length ?? 0;
  const content = rowMarkdown(reply, false);
  const settled = preprocessSettledMarkdown(content, pre, mathFormat, {});
  return { stats, settled };
}
