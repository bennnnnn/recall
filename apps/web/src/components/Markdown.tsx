import { useMemo } from "react";
import { marked } from "marked";
import DOMPurify from "dompurify";

// Plain markdown rendering for assistant text (slice 1). No KaTeX, Mermaid,
// Vega, or HTML iframe — those rich fences come in a later slice. Math/graph
// fences render as plain code blocks here, which is acceptable for slice 1.
//
// chat-ux-bans: assistant bodies are NOT folded (no Show more / Show less).
// The full body is rendered inline.
marked.setOptions({ breaks: true, gfm: true });

// Allowlist for the sanitized HTML. marked emits a small, safe tag set by
// default; DOMPurify strips anything else (e.g. <script>, event handlers) so
// a model-emitted <img onerror=...> can't run in the browser.
const SANITIZE_CONFIG = {
  ALLOWED_TAGS: [
    "p", "br", "hr", "strong", "em", "del", "code", "pre",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "ul", "ol", "li", "blockquote",
    "a", "span",
  ],
  ALLOWED_ATTR: ["href", "target", "rel"],
};

export function renderMarkdown(markdown: string): string {
  const rawHtml = marked.parse(markdown ?? "", { async: false }) as string;
  return DOMPurify.sanitize(rawHtml, SANITIZE_CONFIG) as unknown as string;
}

export function Markdown({ content }: { content: string }) {
  const html = useMemo(() => renderMarkdown(content), [content]);
  return (
    <div
      className="markdown"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
