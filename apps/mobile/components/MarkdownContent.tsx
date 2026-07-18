/** Markdown renderer — v2 (no nested Markdown / plainFence), theme-aware. */
import React, { useEffect, useMemo, useRef, useState } from "react";
import { StyleSheet, Text } from "react-native";
import Markdown from "react-native-markdown-display";

import { CodeBlock } from "@/components/CodeBlock";
import { makeRenderRules } from "@/components/markdown/markdownRenderRules";
import { markdownItInstance } from "@/lib/markdownIt";
import { preprocessMarkdown } from "@/lib/markdownPreprocess";
import {
  preprocessMarkdownForStream,
  type StreamingPreprocessCache,
} from "@/lib/markdownPreprocessStream";
import {
  advanceStreamBlocks,
  type StreamBlocksState,
} from "@/lib/markdownStreamBlocks";
import { classifyOpenStreamTail } from "@/lib/streamingOpenFence";
import {
  nextStreamUiFlushDelay,
  STREAM_UI_INTERVAL_MS,
} from "@/lib/streamUiTiming";
import { CODE_FONT } from "@/lib/fonts";
import { Theme, useTheme } from "@/lib/theme";

type Props = { content: string; streaming?: boolean };

type MarkdownChunkProps = {
  content: string;
  rules: ReturnType<typeof makeRenderRules>["rules"];
  mdStyles: ReturnType<typeof makeRenderRules>["mdStyles"];
};

/**
 * One settled chunk of a streaming reply. Chunk strings never change while a
 * reply streams (append-only), so each chunk parses and mounts exactly once —
 * per-flush work stays proportional to the live tail, not the whole message.
 */
const MarkdownStreamChunk = React.memo(function MarkdownStreamChunk({
  content,
  rules,
  mdStyles,
}: MarkdownChunkProps) {
  return (
    <Markdown style={mdStyles} rules={rules as never} markdownit={markdownItInstance}>
      {content}
    </Markdown>
  );
});

/** Open $$ / \[ body — plain text until the closer arrives (no KaTeX WebView). */
const StreamingMathPreview = React.memo(function StreamingMathPreview({
  body,
}: {
  body: string;
}) {
  const theme = useTheme();
  const s = useMemo(() => makeMathPreviewStyles(theme), [theme]);
  return (
    <Text style={s.body} selectable>
      {body.length > 0 ? body : " "}
    </Text>
  );
});

export function MarkdownContent({ content, streaming = false }: Props) {
  const t = useTheme();
  const { rules, mdStyles } = useMemo(() => makeRenderRules(t, streaming), [t, streaming]);
  // While streaming, throttle re-parses. Settled chunks parse once ever, so
  // only the small tail is re-tokenized per flush — a short interval keeps
  // text appearing fluidly without whole-message parse cost. The trailing
  // flush ensures the final render is always the complete content.
  // Non-streaming renders parse immediately (no throttle).
  const [throttled, setThrottled] = useState(content);
  const lastFlushRef = useRef(0);
  const streamPreprocessRef = useRef<StreamingPreprocessCache | null>(null);
  const streamBlocksRef = useRef<StreamBlocksState | null>(null);
  useEffect(() => {
    if (!streaming) {
      streamPreprocessRef.current = null;
      streamBlocksRef.current = null;
    }
  }, [streaming]);
  useEffect(() => {
    if (!streaming) {
      setThrottled(content);
      return;
    }
    const elapsed = Date.now() - lastFlushRef.current;
    const wait = nextStreamUiFlushDelay(elapsed, STREAM_UI_INTERVAL_MS);
    if (wait === 0) {
      lastFlushRef.current = Date.now();
      setThrottled(content);
      return;
    }
    const id = setTimeout(() => {
      lastFlushRef.current = Date.now();
      setThrottled(content);
    }, wait);
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

  if (streaming) {
    // Settling only happens inside the prepared-stable prefix, whose
    // preprocessing is final; the raw remainder stays in the live tail.
    const cache = streamPreprocessRef.current;
    const safeLen = cache?.preparedStable.length ?? 0;
    const blocks = advanceStreamBlocks(streamBlocksRef.current, prepared, safeLen);
    streamBlocksRef.current = blocks;
    const settledEnd = blocks.settledText.length;
    // Closed-but-not-yet-chunked prefix still goes through markdown-it (small).
    const unsettledStable = prepared.slice(settledEnd, safeLen);
    const liveRaw = prepared.slice(safeLen);
    const openRegion = classifyOpenStreamTail(liveRaw, cache?.scanState);

    return (
      <>
        {blocks.chunks.map((chunk, index) => (
          <MarkdownStreamChunk
            key={`chunk-${index}`}
            content={chunk}
            rules={rules}
            mdStyles={mdStyles}
          />
        ))}
        {unsettledStable ? (
          <Markdown style={mdStyles} rules={rules as never} markdownit={markdownItInstance}>
            {unsettledStable}
          </Markdown>
        ) : null}
        {openRegion.kind === "fence" ? (
          <CodeBlock code={openRegion.body} lang={openRegion.lang} streaming />
        ) : openRegion.kind === "math" ? (
          <StreamingMathPreview body={openRegion.body} />
        ) : openRegion.text ? (
          <Markdown style={mdStyles} rules={rules as never} markdownit={markdownItInstance}>
            {openRegion.text}
          </Markdown>
        ) : null}
      </>
    );
  }

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

function makeMathPreviewStyles(theme: Theme) {
  return StyleSheet.create({
    body: {
      fontFamily: CODE_FONT,
      fontSize: 15,
      lineHeight: 22,
      color: theme.text,
      marginVertical: 4,
    },
  });
}
