import { Text } from "react-native";

import { CodeBlock } from "@/components/CodeBlock";
import { CopyBlock } from "@/components/CopyBlock";
import { AnswerBlock } from "@/components/rich/AnswerBlock";
import {
  LazyCircularClockBlock,
  LazyWebPreviewCodeBlock,
} from "@/components/rich/LazyHeavyRich";
import { MathBlock } from "@/components/rich/MathView";
import {
  renderCopyStyleBlock,
  renderRichFenceById,
} from "@/components/rich/RichFence";
import { splitAnswerNotation } from "@/lib/answerNotation";
import { copyBlockLabelKey, draftFenceProseText } from "@/lib/copyBlock";
import { parseFenceLang } from "@/lib/codeHighlight";
import { isNeverCodeBlockLang } from "@/lib/fenceRegistry";
import {
  classifyFence,
  looksLikeMathMeta,
  shouldHideCopyOnCodeFallback,
} from "@/lib/fenceDispatch";
import { PARAGRAPH_GAP } from "@/components/markdown/markdownContentStyles";
import { useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

// `tokenIndex` (and `index`) come from react-native-markdown-display's AST
// (tokensToAST.js) — unlike `key` (a never-reset getUniqueID counter that
// changes every re-parse), they are stable across re-parses for an
// already-emitted fence. Optional because tests/fakes construct FenceNodes
// directly without them.
export type FenceNode = {
  key: string;
  content: string;
  // react-native-markdown-display's AST (tokensToAST.js) exposes the fence's
  // language tag as `sourceInfo`, not `info` — reading `.info` here silently
  // returned undefined for every fence, dropping the model's explicit
  // ```answer / ```math / ```geometry / code-language tags before any of the
  // lang-based routing below ever saw them.
  sourceInfo?: string;
  tokenIndex?: number;
  index?: number;
};

/** Prose from a draft fence, drawn like a reply paragraph (it had no color, so black in dark mode). */
function NeverCodeBlockFallback({ content }: { content: string }) {
  const t = useTheme();
  return (
    <Text selectable style={[Type.body, { color: t.assistantText, marginBottom: PARAGRAPH_GAP }]}>
      {content}
    </Text>
  );
}

function neverCodeBlockFallback(key: string, content: string) {
  return <NeverCodeBlockFallback key={key} content={content} />;
}

function renderFenceInner(
  key: string,
  lang: string,
  content: string,
  tokenIndex?: number,
  streaming = false,
) {
  const decision = classifyFence(lang, content);

  if (decision.kind === "hide") return null;

  if (decision.kind === "html") {
    return <LazyWebPreviewCodeBlock key={key} code={content} lang={lang || "html"} />;
  }

  if (decision.kind === "answer") {
    return <AnswerBlock key={key} content={content} settled={!streaming} />;
  }

  // An ```answer fence without the server's mark shows its value as ordinary
  // math or text: never its header lines, never the card.
  const shown = decision.id === "answer" ? splitAnswerNotation(content).body : content;

  if (decision.kind === "math") {
    const mathKey =
      tokenIndex != null ? `math:${shown}#${tokenIndex}` : `math:${shown}`;
    return <MathBlock key={mathKey} latex={shown} />;
  }

  if (decision.kind === "clock") {
    return <LazyCircularClockBlock key={key} content={content} />;
  }

  if (decision.kind === "prose") {
    const prose = decision.id === "answer" ? shown : draftFenceProseText(content);
    return prose ? neverCodeBlockFallback(key, prose) : null;
  }

  if (decision.kind === "rich" && decision.id) {
    const rich = renderRichFenceById(decision.id, lang, content, key, tokenIndex);
    if (rich) return rich;
    if (isNeverCodeBlockLang(lang)) return neverCodeBlockFallback(key, content);
  }

  const copyStyle = renderCopyStyleBlock(lang, content, key, tokenIndex);
  if (copyStyle) return copyStyle;

  if (decision.kind === "copy") {
    const styled = renderCopyStyleBlock("copy", content, key, tokenIndex);
    if (styled) return styled;
    return <CopyBlock key={key} text={content} labelKey={copyBlockLabelKey(lang)} />;
  }

  if (isNeverCodeBlockLang(lang)) return neverCodeBlockFallback(key, content);

  return (
    <CodeBlock
      key={key}
      code={content}
      lang={lang}
      showCopy={!shouldHideCopyOnCodeFallback(lang, content)}
    />
  );
}

/** Render rule for a settled reply (the markdown library passes more arguments). */
export function renderSettledFence(node: FenceNode) {
  return renderFence(node);
}

/** Render rule for a reply that is still streaming: never an answer check. */
export function renderStreamingFence(node: FenceNode) {
  return renderFence(node, { streaming: true });
}

export function renderFence(node: FenceNode, options: { streaming?: boolean } = {}) {
  const lang = parseFenceLang(node.sourceInfo?.trim() || "");
  const content = node.content.replace(/\n$/, "").trim();
  if (!content) return null;

  try {
    return renderFenceInner(node.key, lang, content, node.tokenIndex, options.streaming);
  } catch (error) {
    if (__DEV__) {
      console.warn("[MarkdownContent] fence render failed", error);
    }
    if (isNeverCodeBlockLang(lang)) {
      return neverCodeBlockFallback(node.key, content);
    }
    return (
      <CodeBlock
        key={node.key}
        code={content}
        lang={lang}
        showCopy={!shouldHideCopyOnCodeFallback(lang, content) && !looksLikeMathMeta(content)}
      />
    );
  }
}
