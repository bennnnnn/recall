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

export type FenceNode = { key: string; content: string; info?: string };

function isMathDiagramLang(lang: string): boolean {
  const l = lang.trim().toLowerCase();
  return l === "graph" || l === "geometry" || l === "math" || l === "latex" || l === "tex";
}

function looksLikeMathMeta(content: string): boolean {
  return /^(Could not render that diagram\.?|Invalid (graph|geometry) block)/i.test(
    content.trim(),
  );
}

function renderFenceInner(key: string, lang: string, content: string) {
  if (shouldUseHtmlPreview(lang, content)) {
    return <WebPreviewCodeBlock key={key} code={content} lang={lang || "html"} />;
  }
  const l = lang.trim().toLowerCase();
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
    return <MathBlock key={`math:${content}`} latex={content} />;
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
  // Short finals / mis-tagged math equations — gray answer or MathBlock, never Copy.
  if (isAnswerLang(l) || looksLikeMathAnswer(content)) {
    return <AnswerBlock key={key} content={content} />;
  }
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
  const lang = parseFenceLang(node.info?.trim() || "");
  const content = node.content.replace(/\n$/, "").trim();
  if (!content) return null;

  try {
    return renderFenceInner(node.key, lang, content);
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
