/** Markdown renderer — v2 (no nested Markdown / plainFence), theme-aware. */
import React, { useEffect, useMemo, useRef } from "react";
import { View } from "react-native";
import Markdown from "react-native-markdown-display";
import Animated, {
  cancelAnimation,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withTiming,
} from "react-native-reanimated";

import { CodeBlock } from "@/components/CodeBlock";
import { AnswerBlock } from "@/components/rich/AnswerBlock";
import { MathText } from "@/components/rich/MathText";
import { makeRenderRules } from "@/components/markdown/markdownRenderRules";
import { markdownItInstance } from "@/lib/markdown/parser";
import { preprocessMarkdown } from "@/lib/markdown/preprocess";
import {
  preprocessMarkdownForStream,
  type StreamingPreprocessCache,
} from "@/lib/markdown/preprocessStream";
import {
  advanceStreamBlocks,
  type StreamBlocksState,
} from "@/lib/markdown/streamBlocks";
import { classifyOpenStreamTail } from "@/lib/streamingOpenFence";
import { classifyOpenFencePreview } from "@/lib/fenceDispatch";
import { hasIncompleteStreamingLatex, prepareStreamingMathText } from "@/lib/math/streaming";
import {
  advancePreviewFilesScan,
  type PreviewScanState,
} from "@/lib/htmlPreviewBundle";
import { HtmlPreviewFilesProvider } from "@/lib/htmlPreviewFiles";
import { draftFenceProseText } from "@/lib/copyBlock";
import { useReduceMotion } from "@/lib/reduceMotion";
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

/** Pulsing placeholder for open math/diagram fences during streaming. */
const StreamingPlaceholder = React.memo(function StreamingPlaceholder({
  height,
}: {
  height: number;
}) {
  const theme = useTheme();
  const reduceMotion = useReduceMotion();
  const opacity = useSharedValue(0.5);
  useEffect(() => {
    cancelAnimation(opacity);
    if (reduceMotion) {
      opacity.value = 0.75;
      return;
    }
    opacity.value = withRepeat(withTiming(1, { duration: 1200 }), -1, true);
    return () => cancelAnimation(opacity);
  }, [opacity, reduceMotion]);
  const pulseStyle = useAnimatedStyle(() => ({ opacity: opacity.value }));
  return (
    <View style={{ marginVertical: 8 }}>
      <Animated.View
        style={[
          {
            width: "100%",
            height,
            borderRadius: 10,
            backgroundColor: theme.border,
          },
          pulseStyle,
        ]}
      />
    </View>
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
  // A \begin{matrix}/\begin{cases}/\begin{aligned} environment that hasn't
  // closed yet renders as a broken partial via MathText (the ENV_RE in
  // mathText.ts requires both \begin and \end), then snaps to the correct
  // layout when \end{…} arrives — a visible blank-then-jump. Hold a quiet
  // box until the environment closes, matching StreamingDiagramPlaceholder.
  if (hasIncompleteStreamingLatex(trimmed)) {
    return <StreamingPlaceholder height={48} />;
  }
  return (
    <View style={{ marginVertical: 4 }}>
      <MathText latex={trimmed} textColor={theme.text} />
    </View>
  );
});

/** Open ```geometry / ```graph — hold a quiet box, never dump JSON into Codeblock. */
const StreamingDiagramPlaceholder = React.memo(function StreamingDiagramPlaceholder() {
  return <StreamingPlaceholder height={96} />;
});

export function MarkdownContent({ content, streaming = false, mathFormat }: Props) {
  const t = useTheme();
  const { rules, mdStyles } = useMemo(() => makeRenderRules(t, streaming), [t, streaming]);
  // Streaming input arrives already throttled at the draft→UI boundary
  // (useStreamingDraft, ~30fps), so parse immediately — a second throttle here
  // only added latency. Settled chunks parse once ever; per flush, only the
  // small tail is re-tokenized.
  const streamPreprocessRef = useRef<StreamingPreprocessCache | null>(null);
  const streamBlocksRef = useRef<StreamBlocksState | null>(null);
  useEffect(() => {
    if (!streaming) {
      streamPreprocessRef.current = null;
      streamBlocksRef.current = null;
    }
  }, [streaming]);
  const renderContent = content;
  // Incremental: streaming content grows append-only, so rescan just the new
  // suffix per flush instead of splitting/scanning the whole message.
  const previewScanRef = useRef<PreviewScanState | null>(null);
  const previewScan = advancePreviewFilesScan(previewScanRef.current, renderContent);
  previewScanRef.current = previewScan;
  const previewFiles = previewScan.files;
  const prepared = useMemo(() => {
    try {
      if (streaming) {
        const { prepared: streamed, cache } = preprocessMarkdownForStream(
          renderContent,
          streamPreprocessRef.current,
          mathFormat,
        );
        streamPreprocessRef.current = cache;
        return streamed;
      }
      return preprocessMarkdown(renderContent, mathFormat);
    } catch {
      return renderContent;
    }
  }, [renderContent, streaming, mathFormat]);

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
    const liveText = openRegion.kind === "other" ? prepareStreamingMathText(openRegion.text) : null;
    const fencePreview =
      openRegion.kind === "fence"
        ? classifyOpenFencePreview(openRegion.lang, openRegion.body)
        : null;

    // Key chunks by content offset + length, not index: chunks are append-only
    // so offsets are stable while one reply streams, and a reset (new stream /
    // regenerate) reusing the same position gets a fresh key instead of
    // recycling a component whose memoized parse belongs to the old reply.
    const chunkOffsets: number[] = [];
    let chunkOffset = 0;
    for (const chunk of blocks.chunks) {
      chunkOffsets.push(chunkOffset);
      chunkOffset += chunk.length;
    }

    return (
      <HtmlPreviewFilesProvider files={previewFiles}>
        {blocks.chunks.map((chunk, index) => (
          <MarkdownStreamChunk
            key={`chunk-${chunkOffsets[index]}-${chunk.length}`}
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
          ) : fencePreview === "prose" ? (
            draftFenceProseText(openRegion.body) ? (
              <Markdown style={mdStyles} rules={rules as never} markdownit={markdownItInstance}>
                {draftFenceProseText(openRegion.body)}
              </Markdown>
            ) : null
          ) : fencePreview === "hide" ? null : fencePreview === "diagram" ? (
            <StreamingDiagramPlaceholder />
          ) : (
            <CodeBlock code={openRegion.body} lang={openRegion.lang} streaming />
          )
        ) : openRegion.kind === "math" ? (
          <StreamingMathPreview body={openRegion.body} />
        ) : liveText ? (
          <>
            {liveText.text ? <Markdown style={mdStyles} rules={rules as never} markdownit={markdownItInstance}>
              {liveText.text}
            </Markdown> : null}
            {liveText.pending ? <StreamingPlaceholder height={32} /> : null}
          </>
        ) : null}
      </HtmlPreviewFilesProvider>
    );
  }

  return (
    <HtmlPreviewFilesProvider files={previewFiles}>
      <Markdown
        style={mdStyles}
        rules={rules as never}
        markdownit={markdownItInstance}
      >
        {prepared}
      </Markdown>
    </HtmlPreviewFilesProvider>
  );
}
