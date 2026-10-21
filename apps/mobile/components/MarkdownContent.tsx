/** Markdown renderer — v2 (no nested Markdown / plainFence), theme-aware. */
import React, { useEffect, useMemo, useRef, type ReactNode } from "react";
import { StyleSheet, View, type StyleProp, type TextStyle } from "react-native";
import Markdown, { type RenderRules } from "react-native-markdown-display";

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

/** What every `Markdown` of one reply is drawn with. */
type MarkdownProps = {
  style: ReturnType<typeof makeRenderRules>["mdStyles"];
  rules: RenderRules;
  markdownit: typeof markdownItInstance;
};

type OpenStreamRegion = ReturnType<typeof classifyOpenStreamTail>;

/**
 * One piece of a streaming reply: a settled chunk, the closed part not yet
 * chunked, or the prose still typing. A settled chunk's string never changes
 * while the reply streams, so it parses and mounts once. The live pieces parse
 * on every flush, and their nodes keep their keys (`withStableNodeKeys`), so a
 * flush updates their views instead of mounting them again.
 *
 * Pieces are keyed by where they start in the prepared text: when the live
 * region is cut into a chunk, the chunk keeps the live piece's views.
 */
const MarkdownPiece = React.memo(function MarkdownPiece({
  content,
  md,
}: {
  content: string;
  md: MarkdownProps;
}) {
  return <Markdown {...md}>{content}</Markdown>;
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

/** Open display maths, the caret after it while it is the last thing drawn. */
function mathTail(body: string, caret: boolean): ReactNode {
  return (
    <View style={mathTailRow}>
      <StreamingMathPreview body={body} />
      {caret ? <StreamingCursor /> : null}
    </View>
  );
}

/**
 * What the still-open end of a streaming reply shows: an open fence as its
 * preview (`classifyOpenFencePreview`), open display maths typeset, or the
 * prose typed so far.
 */
function openTail(
  region: OpenStreamRegion,
  preview: OpenFencePreviewKind | null,
  prose: string,
  caretOnMath: boolean,
  md: MarkdownProps,
): ReactNode {
  const proseBlock = prose.trim() ? <MarkdownPiece key="tail" content={prose} md={md} /> : null;
  if (region.kind === "math") return mathTail(region.body, caretOnMath);
  if (region.kind !== "fence") return proseBlock;
  switch (preview) {
    case "answer":
      return region.body.trim() ? <AnswerBlock content={region.body} settled={false} /> : null;
    case "math":
      return mathTail(region.body, caretOnMath);
    case "prose":
      return proseBlock;
    case "hide":
    case "placeholder":
      return null;
    default:
      return <CodeBlock code={region.body} lang={region.lang} streaming />;
  }
}

const LEADING_HEADING = /^\s*(#{1,6})[ \t]/;

/**
 * A reply that opens with a heading should not open with that heading's top
 * margin. Read from the source, so the streaming and settled renders agree and
 * nothing jumps when the reply finishes.
 */
function leadingHeadingMargin(
  text: string,
  styles: Readonly<Record<string, StyleProp<TextStyle>>>,
): number {
  const match = LEADING_HEADING.exec(text);
  if (!match) return 0;
  const style = StyleSheet.flatten(styles[`heading${match[1].length}`]);
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
  const { rules, continuedRules, mdStyles: replyStyles } = useMemo(
    () => makeRenderRules(t, streaming),
    [t, streaming],
  );
  const mdStyles = useMemo(
    () => (compact ? compactMdStyles(replyStyles) : replyStyles),
    [compact, replyStyles],
  );
  const md = useMemo<MarkdownProps>(
    () => ({ style: mdStyles, rules, markdownit: markdownItInstance }),
    [mdStyles, rules],
  );
  const mdContinued = useMemo<MarkdownProps>(
    () => ({ style: mdStyles, rules: continuedRules, markdownit: markdownItInstance }),
    [mdStyles, continuedRules],
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
    // One keyed list, so the chunk cut from the live piece keeps its views.
    const pieces: { start: number; content: string; continued: boolean }[] = [];
    let start = 0;
    blocks.chunks.forEach((chunk, index) => {
      pieces.push({ start, content: chunk, continued: blocks.continued[index] === true });
      start += chunk.length;
    });
    if (unsettledShown) pieces.push({ start: settledEnd, content: unsettledShown, continued: false });

    return (
      <HtmlPreviewFilesProvider files={previewFiles}>
        <View style={leadingOffset}>
        {pieces.map((piece) => (
          <MarkdownPiece
            key={`piece-${piece.start}`}
            content={piece.content}
            md={piece.continued ? mdContinued : md}
          />
        ))}
        {openTail(openRegion, fencePreview, proseShown, caretOnMath, md)}
        {caretHost === "after" && !caretOnMath ? <StreamingCursor /> : null}
        </View>
      </HtmlPreviewFilesProvider>
    );
  }

  return (
    <HtmlPreviewFilesProvider files={previewFiles}>
      <View style={leadingOffset}>
        <Markdown {...md}>{prepared}</Markdown>
      </View>
    </HtmlPreviewFilesProvider>
  );
}
