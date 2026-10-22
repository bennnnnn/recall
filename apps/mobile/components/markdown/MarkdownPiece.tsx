import React from "react";
import Markdown, { type RenderRules } from "react-native-markdown-display";

import type { makeRenderRules } from "@/components/markdown/markdownRenderRules";
import type { markdownItInstance } from "@/lib/markdown/parser";

/** What every `Markdown` of one reply is drawn with. */
export type MarkdownProps = {
  style: ReturnType<typeof makeRenderRules>["mdStyles"];
  rules: RenderRules;
  markdownit: typeof markdownItInstance;
};

/**
 * One piece of a reply: a settled chunk, or the live end after the chunks. A
 * settled chunk's string never changes while the reply streams, so it parses
 * and mounts once. The live piece parses on every flush, and its nodes keep
 * their keys (`withStableNodeKeys`), so a flush updates its views instead of
 * mounting them again.
 *
 * Pieces are keyed by where they start in the prepared text: when the live
 * region is cut into a chunk, the chunk keeps the live piece's views, and when
 * the reply settles its pieces keep theirs.
 */
export const MarkdownPiece = React.memo(function MarkdownPiece({
  content,
  md,
}: {
  content: string;
  md: MarkdownProps;
}) {
  return <Markdown {...md}>{content}</Markdown>;
});
