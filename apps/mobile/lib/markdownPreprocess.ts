import { parseQuoteAttribution, isStructuredFenceLang } from "@/lib/richBlocks";
import {
  isExplicitCodeLang,
  looksLikeCode,
  shouldRenderAsPlainProseFence,
} from "@/lib/copyBlock";
import { parseFenceLang } from "@/lib/codeHighlight";

const CALLOUT_RE = /^>\s*\[!(\w+)\]\s*([^\n]*)\n((?:>\s?.*\n?)*)/gim;
const BLOCK_MATH_RE = /\$\$([\s\S]+?)\$\$/g;
const DETAILS_HTML_RE =
  /<details>\s*<summary>([\s\S]*?)<\/summary>\s*([\s\S]*?)<\/details>/gim;
const FENCED_TABLE_RE =
  /```(?:markdown|md|table|text)?\s*\n((?:[^\n]*\|[^\n]*\n){2,})```/gi;
const FENCE_BLOCK_RE = /```([^\n]*)\n([\s\S]*?)```/g;

function isPipeRow(line: string): boolean {
  const t = line.trim();
  return t.includes("|") && /^\|.+\|$/.test(t);
}

function isLoosePipeRow(line: string): boolean {
  const t = line.trim();
  if (!t.includes("|") || isDividerLine(t)) return false;
  const cells = t
    .split("|")
    .map((c) => c.trim())
    .filter((c) => c.length > 0);
  return cells.length >= 2;
}

function isTableRow(line: string): boolean {
  return isPipeRow(line) || isLoosePipeRow(line);
}

/** Lines the model uses instead of proper table rows: ---, ___, ===, etc. */
function isDividerLine(line: string): boolean {
  const t = line.trim();
  if (!t) return false;
  if (/^[-–—_=*~]{3,}$/.test(t)) return true;
  if (/^(\s*[-–—_=*~]\s*){3,}$/.test(t)) return true;
  return false;
}

function isSeparatorRow(line: string): boolean {
  return /^\|(\s*:?\s*-+\s*:?\s*\|)+\s*$/.test(line.trim());
}

function toStrictPipeRow(line: string): string {
  const t = line.trim();
  if (isPipeRow(t)) return t;
  let parts = t.split("|").map((c) => c.trim());
  if (parts[0] === "") parts = parts.slice(1);
  if (parts[parts.length - 1] === "") parts = parts.slice(0, -1);
  return `| ${parts.join(" | ")} |`;
}

function separatorForHeader(headerLine: string): string {
  const strict = toStrictPipeRow(headerLine);
  const cols = strict.split("|").filter((c) => c.trim().length > 0);
  return `|${cols.map(() => " --- ").join("|")}|`;
}

function isGhostTableRow(line: string): boolean {
  if (!isTableRow(line)) return false;
  const strict = toStrictPipeRow(line);
  const cells = strict
    .split("|")
    .map((c) => c.trim())
    .filter((c) => c.length > 0);
  return cells.length > 0 && cells.every((c) => /^[-–—_]+$/.test(c));
}

function finalizePipeTable(rows: string[]): string[] {
  const strict = rows.map(toStrictPipeRow).filter((r) => !isGhostTableRow(r));
  if (strict.length < 2) return rows;

  const out: string[] = [strict[0]];
  if (strict.length > 1 && isSeparatorRow(strict[1])) {
    out.push(strict[1], ...strict.slice(2));
  } else {
    out.push(separatorForHeader(strict[0]), ...strict.slice(1));
  }
  return out;
}

/** Strip ASCII dividers, normalize loose pipe rows, build valid GFM tables. */
export function normalizeMarkdownTables(content: string): string {
  let out = content;

  out = out.replace(
    FENCED_TABLE_RE,
    (_m, table: string) => `\n${table.trim()}\n`,
  );

  out = out
    .split("\n")
    .filter((line) => !/^\+[-=+]+\+$/.test(line.trim()))
    .join("\n");

  const lines = out.split("\n");
  const fixed: string[] = [];
  let tableBuffer: string[] = [];

  const flushTable = () => {
    if (tableBuffer.length >= 2) {
      fixed.push(...finalizePipeTable(tableBuffer));
    } else {
      fixed.push(...tableBuffer);
    }
    tableBuffer = [];
  };

  for (const line of lines) {
    if (isDividerLine(line)) continue;

    if (isTableRow(line)) {
      if (isGhostTableRow(line)) continue;
      tableBuffer.push(line);
      continue;
    }

    flushTable();
    fixed.push(line);
  }
  flushTable();

  return fixed.join("\n");
}

/** True when fenced/plain content is a GFM pipe table (not prose). */
export function isPipeTable(content: string): boolean {
  const normalized = normalizeMarkdownTables(content);
  const lines = normalized
    .trim()
    .split("\n")
    .filter((l) => l.trim());
  if (lines.length < 2) return false;
  const pipeRows = lines.filter(isPipeRow);
  return pipeRows.length >= 2 && pipeRows.length / lines.length >= 0.6;
}

/**
 * Hoist prose/table fences into inline markdown so we never nest `<Markdown>` inside
 * fence render rules (that caused stack overflows and stripped formatting).
 */
function unwrapNonCodeFences(content: string): string {
  return content.replace(FENCE_BLOCK_RE, (full, info: string, body: string) => {
    const lang = parseFenceLang((info || "").trim());
    const l = lang.toLowerCase();
    if (isStructuredFenceLang(l) || l === "details" || l === "math") {
      return full;
    }

    const trimmed = body.replace(/\n$/, "").trim();

    // Drop empty/whitespace fences — they render as blank gray boxes.
    if (!trimmed) return "";

    if (isExplicitCodeLang(lang) || looksLikeCode(trimmed)) {
      return full;
    }

    if (isPipeTable(trimmed)) {
      return `\n${normalizeMarkdownTables(trimmed)}\n`;
    }

    if (shouldRenderAsPlainProseFence(lang, trimmed)) {
      return `\n\n${trimmed}\n\n`;
    }

    return full;
  });
}

/** GitHub callouts, block math, and HTML details → fenced blocks the app understands. */
export function preprocessMarkdown(content: string): string {
  let out = content;

  out = out.replace(
    CALLOUT_RE,
    (_match, kind: string, title: string, body: string) => {
      const k = kind.trim().toLowerCase();
      const cleaned = body
        .split("\n")
        .map((line) => line.replace(/^>\s?/, ""))
        .join("\n")
        .trim();
      const heading = title.trim();
      const merged = heading ? `${heading}\n\n${cleaned}` : cleaned;
      return `\n\`\`\`callout-${k}\n${merged}\n\`\`\`\n`;
    },
  );

  out = out.replace(DETAILS_HTML_RE, (_m, title: string, body: string) => {
    return `\n\`\`\`details ${title.trim()}\n${body.trim()}\n\`\`\`\n`;
  });

  out = out.replace(BLOCK_MATH_RE, (_m, latex: string) => {
    return `\n\`\`\`math\n${latex.trim()}\n\`\`\`\n`;
  });

  out = normalizeMarkdownTables(out);

  // Re-tag fences that contain Vega / Vega-Lite specs so ChartBlock renders them.
  out = out.replace(
    /```(?:json|vega|vega-lite|chart|plot)?\s*\n(\s*\{[\s\S]*?"\$schema"\s*:\s*"https?:\/\/vega\.github\.io\/schema\/(?:vega-lite|vega)\/[\s\S]*?\}\s*)```/gi,
    (_m, body: string) => `\`\`\`vega-lite\n${body.trim()}\n\`\`\``,
  );

  // Wrap bare Vega-Lite JSON blocks (not in fences) so they render as charts.
  out = out.replace(
    /(?:^|\n\n)(\{\s*"\$schema"\s*:\s*"https?:\/\/vega\.github\.io\/schema\/(?:vega-lite|vega)\/v\d+\.json"[\s\S]*?\n\})/g,
    (_m: string, body: string) => `\n\n\`\`\`vega-lite\n${body.trim()}\n\`\`\`\n\n`,
  );

  out = unwrapNonCodeFences(out);

  return out;
}

export function extractBlockquoteMeta(raw: string): {
  quote: string;
  author?: string;
} {
  return parseQuoteAttribution(raw);
}

/** Split paragraph text into plain + inline math segments. */
export function splitInlineMath(
  text: string,
): Array<{ type: "text" | "math"; value: string }> {
  const parts: Array<{ type: "text" | "math"; value: string }> = [];
  const re = /\$([^$\n]+?)\$/g;
  let last = 0;
  let match: RegExpExecArray | null;
  while ((match = re.exec(text)) !== null) {
    if (match.index > last) {
      parts.push({ type: "text", value: text.slice(last, match.index) });
    }
    parts.push({ type: "math", value: match[1].trim() });
    last = match.index + match[0].length;
  }
  if (last < text.length) {
    parts.push({ type: "text", value: text.slice(last) });
  }
  return parts.length ? parts : [{ type: "text", value: text }];
}
