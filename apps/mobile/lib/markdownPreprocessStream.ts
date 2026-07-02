import { preprocessMarkdown } from "@/lib/markdownPreprocess";

export type StreamingPreprocessCache = {
  /** Raw byte length covered by `preparedStable`. */
  rawStableLen: number;
  /** Preprocessed output for `content.slice(0, rawStableLen)`. */
  preparedStable: string;
};

/**
 * Longest raw prefix safe to preprocess while the message is still growing.
 * Excludes partial lines and regions inside unclosed fences / block math.
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
  if (/\n>\s*\[!(\w+)\][^\n]*\n(?:>\s?.*\n)*$/i.test(text)) return true;
  return false;
}

function countFenceMarkers(text: string): number {
  const matches = text.match(/^```/gm);
  return matches?.length ?? 0;
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

/**
 * Incrementally preprocess append-only streaming markdown.
 * Stable prefix is fully preprocessed; the trailing unstable region stays raw
 * until it closes (or the stream ends and a full preprocess runs).
 */
export function preprocessMarkdownForStream(
  content: string,
  cache: StreamingPreprocessCache | null,
): { prepared: string; cache: StreamingPreprocessCache } {
  const stableLen = findStableMarkdownPrefixLen(content);

  if (stableLen === 0) {
    return { prepared: content, cache: { rawStableLen: 0, preparedStable: "" } };
  }

  if (stableLen === content.length) {
    const prepared = preprocessMarkdown(content);
    return { prepared, cache: { rawStableLen: stableLen, preparedStable: prepared } };
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
    cache: { rawStableLen: stableLen, preparedStable },
  };
}
