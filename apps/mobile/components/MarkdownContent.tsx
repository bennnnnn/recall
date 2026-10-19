/** Markdown renderer — v2 (no nested Markdown / plainFence), theme-aware. */
import React, { useEffect, useMemo, useRef } from "react";
import { StyleSheet, View } from "react-native";
import Markdown from "react-native-markdown-display";

import { CodeBlock } from "@/components/CodeBlock";
import { AnswerBlock } from "@/components/rich/AnswerBlock";
import { MathText } from "@/components/rich/MathText";
import { StreamingCursor, withStreamCaret } from "@/components/StreamingCursor";
import { compactMdStyles } from "@/components/markdown/markdownContentStyles";
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
import { classifyOpenFencePreview, type OpenFencePreviewKind } from "@/lib/fenceDispatch";
import { completeStreamingLatex, prepareStreamingMathText } from "@/lib/math/streaming";
import {
  advancePreviewFilesScan,
  type PreviewScanState,
} from "@/lib/htmlPreviewBundle";
import { HtmlPreviewFilesProvider } from "@/lib/htmlPreviewFiles";
import { draftFenceProseText } from "@/lib/copyBlock";
import { useTheme } from "@/lib/theme";
import { Space } from "@/lib/space";

type Props = {
  content: string;
  streaming?: boolean;
  mathFormat?: (expr: string) => string;
  /** A sent bubble: no space under the last block, so the padding is even. */
  compact?: boolean;
  /** The server presented `content` before saving it (isServerPresentedRow). */
  presented?: boolean;
};

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

/** Open $$ / \[ body — native MathText until the closer arrives (no KaTeX WebView).
 * An unfinished command stays blank. A closed prefix still draws. */
const StreamingMathPreview = React.memo(function StreamingMathPreview({
  body,
}: {
  body: string;
}) {
  const theme = useTheme();
  const drawable = completeStreamingLatex(body);
  if (!drawable) return null;
  return (
    <View style={{ marginVertical: Space.xxs }}>
      <MathText latex={drawable} textColor={theme.text} />
    </View>
  );
});

const mathTailRow = {
  flexDirection: "row" as const,
  flexWrap: "wrap" as const,
  alignItems: "flex-end" as const,
};

function acceptsStreamCaret(markdown: string): boolean {
  const body = markdown.replace(/\s+$/, "");
  return Boolean(body) && !/(?:```|~~~)\s*$/.test(body);
}

function tailPaintsBlock(kind: "fence" | "math" | "other", preview: OpenFencePreviewKind | null): boolean {
  if (kind === "math") return true;
  if (kind !== "fence" || preview == null) return false;
  return preview === "answer" || preview === "math" || preview === "code";
}

const LEADING_HEADING = /^\s*(#{1,6})[ \t]/;

/**
 * A reply that opens with a heading should not open with that heading's top
 * margin. Read from the source, so the streaming and settled renders agree and
 * nothing jumps when the reply finishes.
 */
function leadingHeadingMargin(text: string, styles: Record<string, unknown>): number {
  const match = LEADING_HEADING.exec(text);
  if (!match) return 0;
  const style = StyleSheet.flatten(styles[`heading${match[1].length}`] as never) as
    | { marginTop?: unknown }
    | undefined;
  return typeof style?.marginTop === "number" ? style.marginTop : 0;
}

export function MarkdownContent({
  content,
  streaming = false,
  mathFormat,
  compact = false,
  presented = false,
}: Props) {
  const t = useTheme();
  const { rules, mdStyles: replyStyles } = useMemo(
    () => makeRenderRules(t, streaming),
    [t, streaming],
  );
  const mdStyles = useMemo(
    () => (compact ? compactMdStyles(replyStyles) : replyStyles),
    [compact, replyStyles],
  );
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
          { presented },
        );
        streamPreprocessRef.current = cache;
        return streamed;
      }
      return preprocessMarkdown(renderContent, mathFormat, { presented });
    } catch {
      return renderContent;
    }
  }, [renderContent, streaming, mathFormat, presented]);

  const leadingTop = leadingHeadingMargin(prepared, mdStyles);
  const leadingOffset = leadingTop > 0 ? { marginTop: -leadingTop } : null;

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

    const proseTail =
      openRegion.kind === "fence" && fencePreview === "prose"
        ? draftFenceProseText(openRegion.body)
        : (liveText?.text ?? "");
    const paintsBlock = tailPaintsBlock(openRegion.kind, fencePreview);
    let caretHost: "prose" | "unsettled" | "after" = "after";
    if (proseTail.trim() && acceptsStreamCaret(proseTail)) caretHost = "prose";
    else if (!paintsBlock && acceptsStreamCaret(unsettledStable)) caretHost = "unsettled";
    const proseShown = caretHost === "prose" ? withStreamCaret(proseTail) : proseTail;
    const unsettledShown =
      caretHost === "unsettled" ? withStreamCaret(unsettledStable) : unsettledStable;
    const caretOnMath =
      caretHost === "after" &&
      (openRegion.kind === "math" || fencePreview === "math");

    return (
      <HtmlPreviewFilesProvider files={previewFiles}>
        <View style={leadingOffset}>
        {blocks.chunks.map((chunk, index) => (
          <MarkdownStreamChunk
            key={`chunk-${chunkOffsets[index]}-${chunk.length}`}
            content={chunk}
            rules={rules}
            mdStyles={mdStyles}
          />
        ))}
        {unsettledShown ? (
          <Markdown style={mdStyles} rules={rules as never} markdownit={markdownItInstance}>
            {unsettledShown}
          </Markdown>
        ) : null}
        {openRegion.kind === "fence" ? (
          fencePreview === "answer" ? (
            openRegion.body.trim() ? (
              <AnswerBlock content={openRegion.body} settled={false} />
            ) : null
          ) : fencePreview === "math" ? (
            <View style={mathTailRow}>
              <StreamingMathPreview body={openRegion.body} />
              {caretOnMath ? <StreamingCursor /> : null}
            </View>
          ) : fencePreview === "prose" ? (
            proseShown.trim() ? (
              <Markdown style={mdStyles} rules={rules as never} markdownit={markdownItInstance}>
                {proseShown}
              </Markdown>
            ) : null
          ) : fencePreview === "hide" || fencePreview === "placeholder" ? null : (
            <CodeBlock code={openRegion.body} lang={openRegion.lang} streaming />
          )
        ) : openRegion.kind === "math" ? (
          <View style={mathTailRow}>
            <StreamingMathPreview body={openRegion.body} />
            {caretOnMath ? <StreamingCursor /> : null}
          </View>
        ) : proseShown.trim() ? (
          <Markdown style={mdStyles} rules={rules as never} markdownit={markdownItInstance}>
            {proseShown}
          </Markdown>
        ) : null}
        {caretHost === "after" && !caretOnMath ? <StreamingCursor /> : null}
        </View>
      </HtmlPreviewFilesProvider>
    );
  }

  return (
    <HtmlPreviewFilesProvider files={previewFiles}>
      <View style={leadingOffset}>
        <Markdown
          style={mdStyles}
          rules={rules as never}
          markdownit={markdownItInstance}
        >
          {prepared}
        </Markdown>
      </View>
    </HtmlPreviewFilesProvider>
  );
}
