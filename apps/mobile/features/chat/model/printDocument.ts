/** Build print-ready HTML documents for PDF export. */

import { splitAnswerNotation } from "@/lib/answerNotation";
import { parseFenceLang } from "@/lib/codeHighlight";
import { fenceIdForLang, isMathFenceLang } from "@/lib/fenceRegistry";
import { fenceAfterLine, readFenceMarker } from "@/lib/mdFenceScan";
import { preprocessMarkdown, splitInlineMath } from "@/lib/markdown/preprocess";
import { fenceToCopyText } from "@/lib/markdown/plain";
import { looksLikePipeRow } from "@/lib/markdown/streamTableHold";
import { latexToHtmlSvg } from "@/lib/math/svgMath";
import { restoreMathEscapes } from "@/lib/math/textMarkers";

function escapeHtml(text: string): string {
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
  pre { background: #F1F5F9; border-radius: 8px; padding: 12px; font-size: 12px; line-height: 1.4; white-space: pre-wrap; word-break: break-word; }
  table { border-collapse: collapse; margin: 0 0 12px; font-size: 13px; }
  th, td { border: 1px solid #E5E7EB; padding: 6px 8px; text-align: left; vertical-align: top; }
  th { background: #F9FAFB; font-weight: 600; }
  .answer { margin: 10px 0 14px; padding: 10px 14px; border: 1px solid #E5E7EB; border-radius: 10px; }
  .answer p, .answer .math-block { margin: 0; }
  code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }
  blockquote { margin: 0 0 12px; padding: 8px 12px; border-left: 3px solid #E5E7EB; color: #6B7280; }
  .empty { font-size: 14px; color: #9CA3AF; }
  .math-block { margin: 12px 0; overflow-x: auto; text-align: center; }
  .math-block svg { max-width: 100%; }
`;

/** Where a formula goes, until the page's formulas are drawn together (MathJax loads async). */
const MATH_SLOT = /<span data-tex="([^"]*)" data-display="([01])"><\/span>/g;

/**
 * A formula's place on the page. The maths comes through the chat's preprocessing, which
 * holds `\`, `_` and `*` as placeholders so markdown leaves them alone; the source
 * characters go back first (KaTeX, which printed before, failed on every `R_1` and `\,`).
 */
function renderPrintMathHtml(latex: string, displayMode: boolean): string {
  const source = restoreMathEscapes(latex).trim();
  if (!source) return "";
  return `<span data-tex="${encodeURIComponent(source)}" data-display="${displayMode ? 1 : 0}"></span>`;
}

/**
 * One formula drawn as the chat draws it (MathJax SVG, every glyph a path, so the PDF
 * needs no font), or, when MathJax cannot, as Copy writes it: never its LaTeX source.
 */
async function printMathHtml(latex: string, display: boolean): Promise<string> {
  const svg = await latexToHtmlSvg(latex, display);
  const inner = svg ?? escapeHtml(fenceToCopyText("math", latex));
  return display ? `<div class="math-block">${inner}</div>` : inner;
}

async function typesetMath(html: string): Promise<string> {
  const slots = [...html.matchAll(MATH_SLOT)];
  const drawn = await Promise.all(
    slots.map(([, tex, display]) => printMathHtml(decodeURIComponent(tex ?? ""), display === "1")),
  );
  let next = 0;
  return html.replace(MATH_SLOT, () => drawn[next++] ?? "");
}

function isPrintMathFenceLang(lang: string): boolean {
  const l = lang.trim().toLowerCase();
  return isMathFenceLang(l) || l === "katex" || l === "asciimath";
}

function wrapPrintDocument(title: string, bodyHtml: string, meta?: string): string {
  const safeTitle = escapeHtml(title.trim() || "Recall report");
  const metaBlock = meta?.trim()
    ? `<p class="meta">${escapeHtml(meta.trim())}</p>`
    : "";
  return `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<style>${PRINT_STYLES}</style>
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
 * Math fences and $...$ / \\(...\\) inline math are typeset as the chat typesets them
 * (MathJax SVG), never dumped as raw LaTeX.
 */
export async function markdownToStructuredPrintHtml(title: string, markdown: string): Promise<string> {
  const body = await typesetMath(structuredPrintBody(markdown));
  return wrapPrintDocument(title, body);
}

/**
 * A paragraph's lines as one `<p>`: soft breaks join with a space; a line ending in two spaces
 * or a backslash is a Markdown hard break, so the app shows the next line under it and so
 * does the PDF.
 */
function paragraphHtml(lines: string[]): string {
  const runs: string[][] = [[]];
  for (const line of lines) {
    const hardBreak = / {2,}$|\\$/.test(line);
    runs[runs.length - 1]!.push(line.replace(/\\$/, "").trim());
    if (hardBreak) runs.push([]);
  }
  const html = runs.map((run) => run.join(" ").trim()).filter(Boolean).map(inlineMarkdownToHtml);
  return html.length ? `<p>${html.join("<br>")}</p>` : "";
}

function structuredPrintBody(markdown: string): string {
  const prepared = preprocessMarkdown(markdown.replace(/\r\n/g, "\n"));
  return renderBlocks(prepared.split("\n")) || `<p class="empty"></p>`;
}

/** Markdown lines as print blocks; a list item's own lines come back through here. */
function renderBlocks(lines: string[], depth = 0): string {
  const parts: string[] = [];
  let i = 0;
  let paragraph: string[] = [];

  const flushParagraph = () => {
    if (!paragraph.length) return;
    const html = paragraphHtml(paragraph);
    paragraph = [];
    if (html) parts.push(html);
  };

  while (i < lines.length) {
    const line = lines[i] ?? "";
    const fence = fenceAfterLine(null, line);
    if (fence) {
      flushParagraph();
      const lang = parseFenceLang(readFenceMarker(line)?.info ?? "");
      i += 1;
      const codeLines: string[] = [];
      while (i < lines.length && fenceAfterLine(fence, lines[i] ?? "") != null) {
        codeLines.push(lines[i] ?? "");
        i += 1;
      }
      i += 1; // closing fence
      const body = codeLines.join("\n");
      if (isPrintMathFenceLang(lang)) {
        parts.push(renderPrintMathHtml(body, true));
      } else if (fenceIdForLang(lang) === "answer") {
        parts.push(answerToHtml(body));
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

    if (looksLikePipeRow(line)) {
      flushParagraph();
      const rows: string[] = [];
      while (i < lines.length && looksLikePipeRow(lines[i] ?? "")) {
        rows.push(lines[i] ?? "");
        i += 1;
      }
      parts.push(pipeTableToHtml(rows));
      continue;
    }

    if (THEMATIC_BREAK.test(line)) {
      flushParagraph();
      parts.push("<hr>");
      i += 1;
      continue;
    }

    if (LIST_ITEM.test(line)) {
      flushParagraph();
      const list = readList(lines, i, depth);
      parts.push(list.html);
      i = list.next;
      continue;
    }

    if (!line.trim()) {
      flushParagraph();
      i += 1;
      continue;
    }

    paragraph.push(line);
    i += 1;
  }
  flushParagraph();

  return parts.join("\n");
}

/** A list item: its indent, its marker ("-" or "3."), and the text after the marker. */
const LIST_ITEM = /^( *)([-*+]|\d{1,9}[.)])\s+(.*)$/;
/** "---", "***" or "* * *": a rule, as the chat draws it; read before a list, which "* * *" also looks like. */
const THEMATIC_BREAK = /^ {0,3}([-*_])(?: *\1){2,} *$/;
/** Lists inside lists past this print as text: a line of a thousand "- " must not overflow the stack. */
const MAX_LIST_DEPTH = 12;

function startsBlock(line: string): boolean {
  return (
    fenceAfterLine(null, line) != null ||
    /^(#{1,4})\s+/.test(line) ||
    /^>/.test(line) ||
    looksLikePipeRow(line) ||
    THEMATIC_BREAK.test(line) ||
    LIST_ITEM.test(line)
  );
}

function leadingSpaces(line: string): number {
  return line.length - line.trimStart().length;
}

/**
 * One list from `start`, read as CommonMark reads it, so the PDF numbers and nests what the
 * chat shows: an item keeps its indented lines (a model writes "1. **Read widely**\" then
 * the paragraph under it), a blank line keeps the item when more of it follows, items of
 * the same kind after a blank line stay one list, and an ordered list starts at its first
 * number. Before, each item's paragraph ended the list, so every item printed as "1."
 * with a stray backslash (2026-11-07).
 */
function readList(lines: string[], start: number, depth: number): { html: string; next: number } {
  const first = LIST_ITEM.exec(lines[start] ?? "")!;
  const indent = first[1].length;
  const ordered = /\d/.test(first[2]);
  // A rule ("* * *") looks like an item but ends the list, as in the chat.
  const sameList = (line: string) => {
    const match = THEMATIC_BREAK.test(line) ? null : LIST_ITEM.exec(line);
    return match != null && match[1].length === indent && /\d/.test(match[2]) === ordered;
  };
  const items: string[][] = [];
  let i = start;
  while (i < lines.length) {
    const item = LIST_ITEM.exec(lines[i] ?? "");
    if (!sameList(lines[i] ?? "")) break;
    const contentIndent = indent + item![2].length + 1;
    const body = [item![3]];
    // The item's own indent, from its first indented line: every line under it loses that
    // much, so a fence indented two spaces under "1." keeps its code's indentation.
    let strip: number | null = null;
    i += 1;
    while (i < lines.length) {
      const line = lines[i] ?? "";
      if (!line.trim()) {
        let next = i;
        while (next < lines.length && !(lines[next] ?? "").trim()) next += 1;
        if (next < lines.length && leadingSpaces(lines[next] ?? "") >= contentIndent) {
          body.push(...lines.slice(i, next).map(() => ""));
          i = next;
          continue;
        }
        break;
      }
      const spaces = leadingSpaces(line);
      if (spaces >= contentIndent || (spaces > indent && !sameList(line))) {
        strip ??= Math.min(spaces, contentIndent);
        body.push(line.slice(Math.min(spaces, strip)));
      } else if (!startsBlock(line) && body[body.length - 1]?.trim()) {
        body.push(line.trim()); // a lazy continuation of the item's paragraph
      } else {
        break;
      }
      i += 1;
    }
    items.push(body);
    let next = i;
    while (next < lines.length && !(lines[next] ?? "").trim()) next += 1;
    if (next > i && sameList(lines[next] ?? "")) i = next;
  }
  const tag = ordered ? "ol" : "ul";
  const number = ordered ? Number.parseInt(first[2], 10) : 1;
  const startAttr = ordered && number !== 1 ? ` start="${number}"` : "";
  const html = items.map((body) => listItemHtml(body, depth + 1)).join("");
  return { html: `<${tag}${startAttr}>${html}</${tag}>`, next: i };
}

/** A tight item (no blank line in it) prints its text bare, as CommonMark does; a loose one keeps its paragraphs. */
function listItemHtml(body: string[], depth: number): string {
  if (depth > MAX_LIST_DEPTH) return `<li>${inlineMarkdownToHtml(body.join(" ").trim())}</li>`;
  const inner = renderBlocks(body, depth);
  const tight = body.every((line) => line.trim() !== "");
  return `<li>${tight ? inner.replace(/^<p>([\s\S]*?)<\/p>/, "$1") : inner}</li>`;
}

/** An answer card: its maths typeset, or its text when it is chemistry or a sentence. */
function answerToHtml(body: string): string {
  const { notation, body: answer } = splitAnswerNotation(body);
  const inner =
    notation === "chemistry"
      ? `<p>${escapeHtml(answer)}</p>`
      : answer.includes("$")
        ? `<p>${inlineMarkdownToHtml(answer)}</p>`
        : renderPrintMathHtml(answer, true);
  return `<div class="answer">${inner}</div>`;
}

function pipeTableToHtml(rows: string[]): string {
  const parsed = rows.map(splitPipeCells);
  const body = parsed.filter((cells) => !cells.every((c) => /^:?-+:?$/.test(c)));
  if (!body.length) return "";
  const header = body[0] ?? [];
  const rest = body.slice(1);
  const th = header.map((c) => `<th>${inlineMarkdownToHtml(c)}</th>`).join("");
  const tr = rest
    .map((cells) => `<tr>${cells.map((c) => `<td>${inlineMarkdownToHtml(c)}</td>`).join("")}</tr>`)
    .join("");
  return `<table><thead><tr>${th}</tr></thead><tbody>${tr}</tbody></table>`;
}

function splitPipeCells(row: string): string[] {
  const raw = row.trim();
  const inner = raw.startsWith("|") ? raw.slice(1) : raw;
  const noTrail = inner.endsWith("|") ? inner.slice(0, -1) : inner;
  return noTrail.split("|").map((cell) => cell.trim());
}

function inlineMarkdownToHtml(text: string): string {
  const segments = splitInlineMath(text);
  return segments
    .map((part) => {
      if (part.type === "math") {
        return renderPrintMathHtml(part.value, false);
      }
      return formatInlineText(restoreMathEscapes(part.value));
    })
    .join("");
}

/**
 * Stands in for a code span while emphasis is read, so `proposal_id` keeps its underscore.
 * Not one of the maths placeholders (`lib/math/textMarkers.ts`, U+E000 to U+E00A).
 */
const CODE_SLOT = "\uE0F0";

/** A backslash before ASCII punctuation (as escapeHtml leaves it) is a Markdown escape. */
const ESCAPED_PUNCTUATION = /\\(&(?:amp|lt|gt|quot);|[!#$%'()*+,\-./:;=?@[\\\]^_`{|}~])/g;

function formatInlineText(text: string): string {
  const codes: string[] = [];
  let out = escapeHtml(text).replace(/`([^`]+)`/g, (_match, code: string) => {
    codes.push(`<code>${code}</code>`);
    return `${CODE_SLOT}${codes.length - 1}${CODE_SLOT}`;
  });
  // "\$5", "\*" and "\(" are what they escape, as the chat shows them, and never emphasis.
  out = out.replace(ESCAPED_PUNCTUATION, (_match, char: string) => {
    codes.push(char);
    return `${CODE_SLOT}${codes.length - 1}${CODE_SLOT}`;
  });
  out = out.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, "$1");
  out = out.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>');
  out = out.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  // Emphasis opens and closes at word edges, as in CommonMark: due_at stays a word.
  out = out.replace(/(^|[^\w])__(?!\s)([^_]+?)__(?!\w)/g, "$1<strong>$2</strong>");
  out = out.replace(/(^|[^\w*])\*(?![\s*])([^*]+?)\*(?![\w*])/g, "$1<em>$2</em>");
  out = out.replace(/(^|[^\w])_(?![\s_])([^_]+?)_(?!\w)/g, "$1<em>$2</em>");
  const slot = new RegExp(`${CODE_SLOT}(\\d+)${CODE_SLOT}`, "g");
  return out.replace(slot, (_match, index: string) => codes[Number(index)] ?? "");
}
