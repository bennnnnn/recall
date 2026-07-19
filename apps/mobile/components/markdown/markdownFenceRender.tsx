import { CodeBlock } from "@/components/CodeBlock";
import { WebPreviewCodeBlock } from "@/components/WebPreviewCodeBlock";
import { CopyBlock } from "@/components/CopyBlock";
import { AnswerBlock } from "@/components/rich/AnswerBlock";
import { CircularClockBlock } from "@/components/rich/CircularClockBlock";
import { MathBlock } from "@/components/rich/MathView";
import { looksLikeLatexFence } from "@/lib/mathFenceRetag";
import {
  renderCopyStyleBlock,
  renderRichFence,
} from "@/components/rich/RichFence";
import {
  copyBlockLabel,
  isAnswerLang,
  isExplicitCodeLang,
  looksLikeMathAnswer,
  shouldRenderAsCodeBlock,
  shouldRenderAsCopyBlock,
} from "@/lib/copyBlock";
import { parseFenceLang, shouldUseHtmlPreview } from "@/lib/codeHighlight";
import {
  isClockFenceBody,
  isDigitalTimeOnly,
  isIanaTimezoneOnly,
} from "@/lib/timeQuestion";

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

function isMathDiagramLang(lang: string): boolean {
  const l = lang.trim().toLowerCase();
  return l === "graph" || l === "geometry" || l === "math" || l === "latex" || l === "tex";
}

function looksLikeMathMeta(content: string): boolean {
  return /^(Could not render that diagram\.?|Invalid (graph|geometry) block)/i.test(
    content.trim(),
  );
}

function isFakeImageGenFence(lang: string): boolean {
  const l = lang.trim().toLowerCase();
  return l === "image" || l === "img" || l === "image-gen" || l === "imagen";
}

function renderFenceInner(
  key: string,
  lang: string,
  content: string,
  tokenIndex?: number,
) {
  // Models sometimes invent ```image {"prompt":"..."} — not a real rich fence;
  // hide it so it never shows as a Copy code box.
  if (isFakeImageGenFence(lang)) return null;

  if (shouldUseHtmlPreview(lang, content)) {
    return <WebPreviewCodeBlock key={key} code={content} lang={lang || "html"} />;
  }
  const l = lang.trim().toLowerCase();
  // Finals before generic math — ```answer / short results get the boxed
  // look. The content heuristic only applies to untagged/mis-tagged fences
  // (```copy, no tag) — an explicit ```math/```graph/```geometry tag is the
  // model's own intent and must never be reinterpreted as a final answer
  // just because the content also happens to look like a short expression.
  if (isAnswerLang(l) || (!isMathDiagramLang(l) && looksLikeMathAnswer(content))) {
    return <AnswerBlock key={key} content={content} />;
  }
  if (
    looksLikeLatexFence(content) &&
    l !== "python" &&
    l !== "javascript" &&
    l !== "graph" &&
    l !== "geometry"
  ) {
    // Content-derived key, not the caller-supplied `key` (which
    // react-native-markdown-display regenerates on every re-parse while
    // streaming) — the same latex across re-parses must map to the same
    // key, or MathBlock's WebView-backed renderer unmounts/remounts (a
    // full WebView reload, visible as a flicker) every ~48ms even though
    // nothing actually changed.
    //
    // `tokenIndex` disambiguates two *different* fences that happen to
    // share identical latex (e.g. `\pm 2` appearing twice in one reply):
    // it's stable across re-parses (deterministic re-tokenization of
    // already-emitted content) but unique per fence, so sibling MathBlocks
    // with the same content no longer collide on a duplicate React key.
    const mathKey =
      tokenIndex != null ? `math:${content}#${tokenIndex}` : `math:${content}`;
    return <MathBlock key={mathKey} latex={content} />;
  }
  if (
    l === "clock" ||
    l === "time" ||
    isDigitalTimeOnly(content) ||
    isIanaTimezoneOnly(content) ||
    (l === "" && isClockFenceBody(content))
  ) {
    return <CircularClockBlock key={key} content={content} />;
  }
  const rich = renderRichFence(lang, content, key);
  if (rich) return rich;
  // Math diagram failures must never become a Copy template.
  if (looksLikeMathMeta(content) || isMathDiagramLang(l)) {
    return (
      <CodeBlock
        key={key}
        code={content}
        lang={lang}
        showCopy={false}
      />
    );
  }
  const copyStyle = renderCopyStyleBlock(lang, content, key);
  if (copyStyle) return copyStyle;
  if (isExplicitCodeLang(lang) || shouldRenderAsCodeBlock(lang, content)) {
    return <CodeBlock key={key} code={content} lang={lang} />;
  }
  if (shouldRenderAsCopyBlock(lang, content)) {
    const styled = renderCopyStyleBlock("copy", content, key);
    if (styled) return styled;
    return <CopyBlock key={key} text={content} label={copyBlockLabel(lang)} />;
  }
  return <CodeBlock key={key} code={content} lang={lang} />;
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
    return (
      <CodeBlock
        key={node.key}
        code={content}
        lang={lang}
        showCopy={!isMathDiagramLang(lang) && !looksLikeMathMeta(content)}
      />
    );
  }
}
