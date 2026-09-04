/** Markdown renderer — v2 (no nested Markdown / plainFence), theme-aware. */
import React, { useEffect, useMemo, useRef, useState } from "react";
import { Animated, View } from "react-native";
import Markdown from "react-native-markdown-display";

import { CodeBlock } from "@/components/CodeBlock";
import { AnswerBlock } from "@/components/rich/AnswerBlock";
import { MathText } from "@/components/rich/MathText";
import { makeRenderRules } from "@/components/markdown/markdownRenderRules";
import { markdownItInstance } from "@/lib/markdownIt";
import { preprocessMarkdown } from "@/lib/markdown/markdownPreprocess";
import {
  preprocessMarkdownForStream,
  type StreamingPreprocessCache,
} from "@/lib/markdown/markdownPreprocessStream";
import {
  advanceStreamBlocks,
  type StreamBlocksState,
} from "@/lib/markdown/markdownStreamBlocks";
import { classifyOpenStreamTail } from "@/lib/streamingOpenFence";
import { classifyOpenFencePreview } from "@/lib/fenceDispatch";
import {
  nextStreamUiFlushDelay,
  STREAM_UI_INTERVAL_MS,
} from "@/lib/streamUiTiming";
import { collectPreviewFiles } from "@/lib/htmlPreviewBundle";
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

/** Pulsing placeholder for open math/diagram fences during streaming.
 *  Uses RN's built-in Animated (no Reanimated worklet dependency). */
const StreamingPlaceholder = React.memo(function StreamingPlaceholder({
  height,
}: {
  height: number;
}) {
  const theme = useTheme();
  const reduceMotion = useReduceMotion();
  const opacity = useRef(new Animated.Value(0.5)).current;
  useEffect(() => {
    if (reduceMotion) {
      opacity.setValue(0.75);
      return;
    }
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(opacity, {
          toValue: 1,
          duration: 1200,
          useNativeDriver: true,
        }),
        Animated.timing(opacity, {
          toValue: 0.5,
          duration: 1200,
          useNativeDriver: true,
        }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [opacity, reduceMotion]);
  return (
    <View style={{ marginVertical: 8 }}>
      <Animated.View
        style={{
          width: "100%",
          height,
          borderRadius: 10,
          backgroundColor: theme.border,
          opacity,
        }}
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
  if (hasUnclosedMathEnv(trimmed)) {
    return <StreamingPlaceholder height={48} />;
  }
  return (
    <View style={{ marginVertical: 4 }}>
      <MathText latex={trimmed} textColor={theme.text} />
    </View>
  );
});

/** True when the body has a \begin{…} without a matching \end{…}. */
function hasUnclosedMathEnv(s: string): boolean {
  const begins = (s.match(/\\begin\{[\w*]+\}/g) ?? []).length;
  const ends = (s.match(/\\end\{[\w*]+\}/g) ?? []).length;
  return begins > ends;
}

/** Open ```geometry / ```graph — hold a quiet box, never dump JSON into Codeblock. */
const StreamingDiagramPlaceholder = React.memo(function StreamingDiagramPlaceholder() {
  return <StreamingPlaceholder height={96} />;
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
  const previewFiles = useMemo(() => collectPreviewFiles(renderContent), [renderContent]);
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
    const fencePreview =
      openRegion.kind === "fence"
        ? classifyOpenFencePreview(openRegion.lang, openRegion.body)
        : null;

    return (
      <HtmlPreviewFilesProvider files={previewFiles}>
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
        ) : openRegion.text ? (
          <Markdown style={mdStyles} rules={rules as never} markdownit={markdownItInstance}>
            {openRegion.text}
          </Markdown>
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
