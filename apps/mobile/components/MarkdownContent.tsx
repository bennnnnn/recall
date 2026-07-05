/** Markdown renderer — v2 (no nested Markdown / plainFence), theme-aware. */
import { useEffect, useMemo, useRef, useState } from "react";
import Markdown from "react-native-markdown-display";

import { makeRenderRules } from "@/components/markdown/markdownRenderRules";
import { markdownItInstance } from "@/lib/markdownIt";
import { preprocessMarkdown } from "@/lib/markdownPreprocess";
import {
  preprocessMarkdownForStream,
  type StreamingPreprocessCache,
} from "@/lib/markdownPreprocessStream";
import { useTheme } from "@/lib/theme";

type Props = { content: string; streaming?: boolean };

export function MarkdownContent({ content, streaming = false }: Props) {
  const t = useTheme();
  const { rules, mdStyles } = useMemo(() => makeRenderRules(t, streaming), [t, streaming]);
  // While streaming, throttle the markdown re-parse so we don't tokenize the
  // whole reply on every token. useDeferredValue alone still re-parses on each
  // deferred tick under fast streams; an explicit ~150ms cadence keeps the UI
  // snappy. The trailing flush ensures the final render is always the complete
  // content. Non-streaming renders parse immediately (no throttle).
  const [throttled, setThrottled] = useState(content);
  const lastFlushRef = useRef(0);
  const streamPreprocessRef = useRef<StreamingPreprocessCache | null>(null);
  useEffect(() => {
    if (!streaming) {
      streamPreprocessRef.current = null;
    }
  }, [streaming]);
  useEffect(() => {
    if (!streaming) {
      setThrottled(content);
      return;
    }
    const now = Date.now();
    const elapsed = now - lastFlushRef.current;
    if (elapsed >= STREAM_PARSE_INTERVAL_MS) {
      lastFlushRef.current = now;
      setThrottled(content);
      return;
    }
    const id = setTimeout(() => {
      lastFlushRef.current = Date.now();
      setThrottled(content);
    }, STREAM_PARSE_INTERVAL_MS - elapsed);
    return () => clearTimeout(id);
  }, [content, streaming]);
  const renderContent = streaming ? throttled : content;
  const prepared = useMemo(() => {
    try {
      if (streaming) {
        const { prepared: streamed, cache } = preprocessMarkdownForStream(
          renderContent,
          streamPreprocessRef.current,
        );
        streamPreprocessRef.current = cache;
        return streamed;
      }
      return preprocessMarkdown(renderContent);
    } catch {
      return renderContent;
    }
  }, [renderContent, streaming]);
  return (
    <Markdown
      style={mdStyles}
      rules={rules as never}
      markdownit={markdownItInstance}
    >
      {prepared}
    </Markdown>
  );
}

// Re-parse at most this often while streaming (ms). Lower = snappier but more
// CPU; higher = cheaper but laggier. 150ms is ~6.7 renders/sec — smooth enough
// for streaming text while avoiding a full markdown-it pass per token.
const STREAM_PARSE_INTERVAL_MS = 150;
