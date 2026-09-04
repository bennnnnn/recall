import { Text } from "react-native";

import { CodeBlock } from "@/components/CodeBlock";
import { WebPreviewCodeBlock } from "@/components/WebPreviewCodeBlock";
import { CopyBlock } from "@/components/CopyBlock";
import { AnswerBlock } from "@/components/rich/AnswerBlock";
import { CircularClockBlock } from "@/components/rich/CircularClockBlock";
import { MathBlock } from "@/components/rich/MathView";
import {
  renderCopyStyleBlock,
  renderRichFenceById,
} from "@/components/rich/RichFence";
import { copyBlockLabel } from "@/lib/copyBlock";
import { parseFenceLang } from "@/lib/codeHighlight";
import { isNeverCodeBlockLang } from "@/lib/fenceRegistry";
import {
  classifyFence,
  looksLikeMathMeta,
  shouldHideCopyOnCodeFallback,
} from "@/lib/fenceDispatch";
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

function neverCodeBlockFallback(key: string, content: string) {
  return (
    <Text key={key} selectable style={Type.body}>
      {content}
    </Text>
  );
}

function renderFenceInner(
  key: string,
  lang: string,
  content: string,
  tokenIndex?: number,
) {
  const decision = classifyFence(lang, content);

  if (decision.kind === "hide") return null;

  if (decision.kind === "html") {
    return <WebPreviewCodeBlock key={key} code={content} lang={lang || "html"} />;
  }

  if (decision.kind === "answer") {
    return <AnswerBlock key={key} content={content} />;
  }

  if (decision.kind === "math") {
    const mathKey =
      tokenIndex != null ? `math:${content}#${tokenIndex}` : `math:${content}`;
    return <MathBlock key={mathKey} latex={content} />;
  }

  if (decision.kind === "clock") {
    return <CircularClockBlock key={key} content={content} />;
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
    return <CopyBlock key={key} text={content} label={copyBlockLabel(lang)} />;
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

export function renderFence(node: FenceNode) {
  const lang = parseFenceLang(node.sourceInfo?.trim() || "");
  const content = node.content.replace(/\n$/, "").trim();
  if (!content) return null;

  try {
    return renderFenceInner(node.key, lang, content, node.tokenIndex);
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
