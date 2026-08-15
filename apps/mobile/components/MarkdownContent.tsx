/** Markdown renderer — v2 (no nested Markdown / plainFence), theme-aware. */
import React, { useEffect, useMemo, useRef, useState } from "react";
import { View } from "react-native";
import Markdown from "react-native-markdown-display";

import { CodeBlock } from "@/components/CodeBlock";
import { AnswerBlock } from "@/components/rich/AnswerBlock";
import { MathText } from "@/components/rich/MathText";
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
import { classifyOpenFencePreview } from "@/lib/copyBlock";
import {
  nextStreamUiFlushDelay,
  STREAM_UI_INTERVAL_MS,
} from "@/lib/streamUiTiming";
import { useTheme } from "@/lib/theme";

type Props = { content: string; streaming?: boolean; mathFormat?: (expr: string) => string };

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

/** Open $$ / \[ body — native MathText until the closer arrives (no KaTeX WebView). */
const StreamingMathPreview = React.memo(function StreamingMathPreview({
  body,
}: {
  body: string;
}) {
  const theme = useTheme();
  const trimmed = body.trim();
  if (!trimmed) {
    return <View style={{ height: 8 }} />;
  }
  return (
    <View style={{ marginVertical: 4 }}>
      <MathText latex={trimmed} textColor={theme.text} />
    </View>
  );
});

/** Open ```geometry / ```graph — hold a quiet box, never dump JSON into CodeBlock. */
const StreamingDiagramPlaceholder = React.memo(function StreamingDiagramPlaceholder() {
  const theme = useTheme();
  return (
    <View
      style={{
        marginVertical: 8,
        minHeight: 96,
        borderRadius: 10,
        backgroundColor: theme.contentSurface,
      }}
    />
  );
});

export function MarkdownContent({ content, streaming = false, mathFormat }: Props) {
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
      return preprocessMarkdown(renderContent, mathFormat);
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
    const fencePreview =
      openRegion.kind === "fence"
        ? classifyOpenFencePreview(openRegion.lang, openRegion.body)
        : null;

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
          fencePreview === "answer" ? (
            openRegion.body.trim() ? (
              <AnswerBlock content={openRegion.body} />
            ) : null
          ) : fencePreview === "math" ? (
            <StreamingMathPreview body={openRegion.body} />
          ) : fencePreview === "diagram" ? (
            <StreamingDiagramPlaceholder />
          ) : (
            <CodeBlock code={openRegion.body} lang={openRegion.lang} streaming />
          )
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
