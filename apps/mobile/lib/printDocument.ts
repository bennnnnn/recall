/** Build print-ready HTML documents for PDF export. */

import katex from "katex";

import { KATEX_CSS } from "@/lib/vendor/katexCss";
import { preprocessMarkdown, splitInlineMath } from "@/lib/markdownPreprocess";

const MATH_FENCE_LANGS = new Set([
  "math",
  "latex",
  "tex",
  "katex",
  "asciimath",
]);

export function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

const PRINT_STYLES = `
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; padding: 28px; color: #111827; line-height: 1.55; }
  h1 { font-size: 24px; margin: 0 0 8px; letter-spacing: -0.3px; }
  h2 { font-size: 16px; margin: 22px 0 10px; color: #111827; border-bottom: 1px solid #E5E7EB; padding-bottom: 6px; }
  h3 { font-size: 15px; margin: 14px 0 4px; }
  p { font-size: 14px; margin: 0 0 10px; }
  .meta { font-size: 12px; color: #6B7280; margin: 0 0 18px; }
  .item { margin: 0 0 14px; padding-bottom: 10px; border-bottom: 1px solid #E5E7EB; }
  .item:last-child { border-bottom: none; }
  .def { font-size: 14px; color: #111827; margin: 2px 0; }
  .example { font-size: 13px; color: #6B7280; font-style: italic; margin: 2px 0; }
  .status { font-size: 11px; font-weight: 600; color: #9CA3AF; text-transform: uppercase; letter-spacing: 0.4px; }
  ul, ol { margin: 0 0 12px; padding-left: 22px; }
  li { font-size: 14px; margin: 0 0 4px; }
  pre { background: #F1F5F9; border-radius: 8px; padding: 12px; overflow-x: auto; font-size: 12px; line-height: 1.4; }
  code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }
  blockquote { margin: 0 0 12px; padding: 8px 12px; border-left: 3px solid #E5E7EB; color: #6B7280; }
  .empty { font-size: 14px; color: #9CA3AF; }
  .math-block { margin: 12px 0; overflow-x: auto; text-align: center; }
  .math-inline { display: inline-block; vertical-align: middle; max-width: 100%; }
  .math-fallback { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 13px; white-space: pre-wrap; }
`;

/** Render LaTeX to KaTeX HTML for print (same engine as in-chat math). */
export function renderPrintMathHtml(latex: string, displayMode: boolean): string {
  const trimmed = latex.trim();
  if (!trimmed) return "";
  try {
    if (trimmed.length > 4000) {
      return `<code class="math-fallback">${escapeHtml(trimmed.slice(0, 200))}…</code>`;
    }
    const body = katex.renderToString(trimmed, {
      throwOnError: false,
      displayMode,
      strict: "ignore",
      output: "html",
      maxSize: 20,
      maxExpand: 500,
    });
    const cls = displayMode ? "math-block" : "math-inline";
    return `<span class="${cls}">${body}</span>`;
  } catch {
    return `<code class="math-fallback">${escapeHtml(trimmed)}</code>`;
  }
}

function isMathFenceLang(lang: string): boolean {
  return MATH_FENCE_LANGS.has(lang.trim().toLowerCase());
}

export function wrapPrintDocument(title: string, bodyHtml: string, meta?: string): string {
  const safeTitle = escapeHtml(title.trim() || "Recall report");
  const metaBlock = meta?.trim()
    ? `<p class="meta">${escapeHtml(meta.trim())}</p>`
    : "";
  return `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<style>${KATEX_CSS}
${PRINT_STYLES}</style>
</head>
<body>
  <h1>${safeTitle}</h1>
  ${metaBlock}
  ${bodyHtml}
</body>
</html>`;
}

/**
 * Convert markdown into structured print HTML (headings, lists, code, paragraphs).
 * Math fences and $...$ / \\(...\\) inline math use KaTeX — same as the chat UI —
 * instead of dumping raw LaTeX into <pre>.
 */
export function markdownToStructuredPrintHtml(title: string, markdown: string): string {
  const prepared = preprocessMarkdown(markdown.replace(/\r\n/g, "\n"));
  const lines = prepared.split("\n");
  const parts: string[] = [];
  let i = 0;
  let paragraph: string[] = [];

  const flushParagraph = () => {
    if (!paragraph.length) return;
    const text = paragraph.join(" ").trim();
    paragraph = [];
    if (text) parts.push(`<p>${inlineMarkdownToHtml(text)}</p>`);
  };

  while (i < lines.length) {
    const line = lines[i] ?? "";
    const fence = line.match(/^```(\w*)\s*$/);
    if (fence) {
      flushParagraph();
      const lang = fence[1] || "";
      i += 1;
      const codeLines: string[] = [];
      while (i < lines.length && !/^```\s*$/.test(lines[i] ?? "")) {
        codeLines.push(lines[i] ?? "");
        i += 1;
      }
      i += 1; // closing fence
      const body = codeLines.join("\n");
      if (isMathFenceLang(lang)) {
        parts.push(renderPrintMathHtml(body, true));
      } else {
        const code = escapeHtml(body);
        const langAttr = lang ? ` class="language-${escapeHtml(lang)}"` : "";
        parts.push(`<pre><code${langAttr}>${code}</code></pre>`);
      }
      continue;
    }

    const heading = line.match(/^(#{1,4})\s+(.+)$/);
    if (heading) {
      flushParagraph();
      const level = Math.min(4, heading[1].length) + 1; // h2–h5 under document h1
      parts.push(`<h${level}>${inlineMarkdownToHtml(heading[2].trim())}</h${level}>`);
      i += 1;
      continue;
    }

    const quote = line.match(/^>\s?(.*)$/);
    if (quote) {
      flushParagraph();
      const quoteLines: string[] = [quote[1]];
      i += 1;
      while (i < lines.length && /^>\s?/.test(lines[i] ?? "")) {
        quoteLines.push((lines[i] ?? "").replace(/^>\s?/, ""));
        i += 1;
      }
      parts.push(`<blockquote><p>${inlineMarkdownToHtml(quoteLines.join(" "))}</p></blockquote>`);
      continue;
    }

    if (/^\s*[-*+]\s+/.test(line)) {
      flushParagraph();
      const items: string[] = [];
      while (i < lines.length && /^\s*[-*+]\s+/.test(lines[i] ?? "")) {
        items.push((lines[i] ?? "").replace(/^\s*[-*+]\s+/, ""));
        i += 1;
      }
      parts.push(`<ul>${items.map((item) => `<li>${inlineMarkdownToHtml(item)}</li>`).join("")}</ul>`);
      continue;
    }

    if (/^\s*\d+\.\s+/.test(line)) {
      flushParagraph();
      const items: string[] = [];
      while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i] ?? "")) {
        items.push((lines[i] ?? "").replace(/^\s*\d+\.\s+/, ""));
        i += 1;
      }
      parts.push(`<ol>${items.map((item) => `<li>${inlineMarkdownToHtml(item)}</li>`).join("")}</ol>`);
      continue;
    }

    if (!line.trim()) {
      flushParagraph();
      i += 1;
      continue;
    }

    paragraph.push(line.trim());
    i += 1;
  }
  flushParagraph();

  const body = parts.join("\n") || `<p class="empty"></p>`;
  return wrapPrintDocument(title, body);
}

function inlineMarkdownToHtml(text: string): string {
  const segments = splitInlineMath(text);
  return segments
    .map((part) => {
      if (part.type === "math") {
        return renderPrintMathHtml(part.value, false);
      }
      return formatInlineText(part.value);
    })
    .join("");
}

function formatInlineText(text: string): string {
  let out = escapeHtml(text);
  out = out.replace(/!\[([^\]]*)\]\([^)]+\)/g, "$1");
  out = out.replace(/\[([^\]]+)\]\([^)]+\)/g, "$1");
  out = out.replace(/`([^`]+)`/g, "<code>$1</code>");
  out = out.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  out = out.replace(/__([^_]+)__/g, "<strong>$1</strong>");
  out = out.replace(/\*([^*]+)\*/g, "<em>$1</em>");
  out = out.replace(/_([^_]+)_/g, "<em>$1</em>");
  return out;
}
