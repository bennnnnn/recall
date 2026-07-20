import { retagMoleculeMathToSmiles } from "@/lib/chemistryFence";
import { retagMathAndDiagramFences } from "@/lib/mathFenceRetag";
import { repairBrokenMarkdownLinks } from "@/lib/placesList";
import { normalizeImplicitMath } from "@/lib/normalizeImplicitMath";
import { parseQuoteAttribution, isStructuredFenceLang } from "@/lib/richBlocks";
import {
  isAnswerLang,
  isExplicitCodeLang,
  looksLikeCode,
  looksLikeMathAnswer,
  shouldRenderAsPlainProseFence,
} from "@/lib/copyBlock";
import { isHtmlFenceLang, parseFenceLang } from "@/lib/codeHighlight";
import { PROTECTED_ESCAPE_MARKER } from "@/lib/mathText";

// Title uses horizontal whitespace only; body lines are `>[^\n]*` (no ReDoS).
const CALLOUT_RE =
  /^>[ \t]*\[!(\w+)\][ \t]*([^\n]*)\n((?:>[^\n]*(?:\n|$))*)/gim;
const BLOCK_MATH_RE = /\$\$([\s\S]+?)\$\$/g;
const BLOCK_MATH_BRACKET_RE = /\\\[([\s\S]+?)\\\]/g;
/** Michelin / restaurant price tiers: ($), ($$), ($$$), ($$$$) — not LaTeX. */
const PRICE_TIER_RE = /\(\s*\$+\s*\)/g;
const PRICE_SHIELD_PREFIX = "\uE000P";
const PRICE_SHIELD_SUFFIX = "\uE001";
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
  // Avoid nested `\s*` / `-+\s*` quantifiers (CodeQL js/redos). Collapse
  // whitespace first, then match a strict pipe + dashes (+ optional colons).
  const compact = line.trim().replace(/\s+/g, "");
  return /^\|(:?-+:?\|)+$/.test(compact) && compact.includes("-");
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
    if (isStructuredFenceLang(l) || l === "details" || l === "math" || isHtmlFenceLang(l)) {
      return full;
    }

    const trimmed = body.replace(/\n$/, "").trim();

    // Drop empty/whitespace fences — they render as blank gray boxes.
    if (!trimmed) return "";

    if (/^\$\)?\s*$/.test(trimmed)) return "";

    if (trimmed.startsWith("$$)\n") || trimmed.startsWith("$)\n")) {
      return `\n\n${trimmed.replace(/^\$\)?\s*\n?/, "")}\n\n`;
    }

    // A final-answer-shaped body (bare number, simplified expression, short
    // assignment) must stay a real fence so renderFence routes it to
    // AnswerBlock — shouldRenderAsPlainProseFence below has no concept of
    // "this looks like a math answer" and would otherwise unwrap it into
    // plain prose text before it ever reaches that dispatch.
    if (isAnswerLang(lang) || looksLikeMathAnswer(trimmed)) {
      return full;
    }

    if (isExplicitCodeLang(lang) || looksLikeCode(trimmed)) {
      return full;
    }

    if (isPipeTable(trimmed)) {
      return `\n${normalizeMarkdownTables(trimmed)}\n`;
    }

    if (shouldRenderAsPlainProseFence(lang, trimmed)) {
      return `\n\n${trimmed}\n\n`;
    }

    if (looksLikeMarkdownListProse(trimmed)) {
      return `\n\n${trimmed}\n\n`;
    }

    return full;
  });
}

/** Numbered/bulleted lists and headings — never code fences. */
export function looksLikeMarkdownListProse(content: string): boolean {
  const lines = content
    .trim()
    .split("\n")
    .filter((l) => l.trim());
  if (lines.length === 0) return false;
  const proseLines = lines.filter((line) => {
    const t = line.trim();
    return (
      /^#{1,6}\s/.test(t) ||
      /^\d+\.\s+\*\*/.test(t) ||
      /^[-*]\s+\*\*/.test(t) ||
      /^\d+\.\s+[A-Z]/.test(t)
    );
  });
  return proseLines.length >= 1;
}

/** Hide ($$) / ($$$) price markers so block-math regex cannot swallow list prose. */
function shieldPriceTiers(content: string): {
  text: string;
  restore: (s: string) => string;
} {
  const saved: string[] = [];
  const text = content.replace(PRICE_TIER_RE, (match) => {
    const idx = saved.length;
    saved.push(match);
    return `${PRICE_SHIELD_PREFIX}${idx}${PRICE_SHIELD_SUFFIX}`;
  });
  return {
    text,
    restore: (s) =>
      s.replace(
        new RegExp(`${PRICE_SHIELD_PREFIX}(\\d+)${PRICE_SHIELD_SUFFIX}`, "g"),
        (_, index) => saved[Number(index)] ?? "",
      ),
  };
}

// A price-tier-split artifact is a stray "$)" (or bare "$") *alone on the
// fence's first line* — not just any body that happens to start with "$".
// A `?` on `)` without also requiring a following newline/end matched any
// legitimate math fence whose body starts with "$" too (e.g. a bare
// equation line normalizeImplicitMath had already wrapped as "$x^2 = 4$"
// before this ran), incorrectly unwrapping real math back to inline text.
const PRICE_TIER_ARTIFACT_LINE_RE = /^\$\)?\s*(?:\n|$)/;
const PRICE_TIER_ARTIFACT_STRIP_RE = /^\$\)?\s*\n?/;

/** Undo mistaken ```math fences that contain markdown lists or price-tier debris. */
function unwrapCorruptedMathFences(content: string): string {
  return content.replace(/```math\n([\s\S]*?)```/gi, (full, body: string) => {
    const trimmed = body.trim();
    if (!trimmed) return "";
    if (
      looksLikeMarkdownListProse(trimmed) ||
      PRICE_TIER_ARTIFACT_LINE_RE.test(trimmed) ||
      /^#{1,6}\s/.test(trimmed) ||
      /^\d+\.\s/.test(trimmed) ||
      /Michelin|restaurant|dining|fare|cuisine/i.test(trimmed)
    ) {
      return `\n\n${trimmed.replace(PRICE_TIER_ARTIFACT_STRIP_RE, "")}\n\n`;
    }
    return full;
  });
}

/** Repair list lines truncated by a prior bad ($$) → math-fence split. */
function repairCorruptedPriceTierMarkdown(content: string): string {
  let out = content.replace(
    /```(?:math)?\n\s*\$\)?\s*\n```/gi,
    "",
  );
  out = out.replace(
    /```(?:math)?\n\s*\$\)?\s*\n([\s\S]*?)```/gi,
    (_full, body: string) => `\n\n${String(body).replace(PRICE_TIER_ARTIFACT_STRIP_RE, "")}\n\n`,
  );

  const lines = out.split("\n");
  const fixed: string[] = [];
  for (let i = 0; i < lines.length; i++) {
    let line = lines[i];
    if (/\(\s*$/.test(line) && !/\(\s*\$/.test(line)) {
      const next = lines[i + 1]?.trim() ?? "";
      if (/^\d+\.\s/.test(next) || next.startsWith("```") || next.startsWith("###")) {
        line = line.replace(/\(\s*$/, "($$$)");
      }
    }
    fixed.push(line);
  }
  return fixed.join("\n");
}

/** Turn `- step ✓` bullets into task-list items so MarkdownContent renders green ticks. */
function normalizeVerificationBullets(content: string): string {
  return content
    .split("\n")
    .map((line) => {
      const match = line.match(/^(\s*[-*+]\s+)(.+?)\s*[✓✔✅]\s*$/u);
      if (!match) return line;
      const body = match[2].trim();
      return `- [x] ${body}`;
    })
    .join("\n");
}

// A backslash immediately followed by an ASCII punctuation character —
// CommonMark's own escapable set (matches markdown-it's rules_inline/escape.mjs).
const MATH_ESCAPE_BACKSLASH_RE = /\\(?=[!"#$%&'()*+,\-./:;<=>?@[\]^_`{|}~])/g;

/**
 * Protect punctuation-led LaTeX commands (`\,` `\;` `\!` `\%` `\_` `\{` `\}` …)
 * inside `$...$` / `\(...\)` math from markdown-it's own CommonMark
 * backslash-escape rule, which runs during inline tokenization and silently
 * drops the backslash before splitInlineMath/MathText ever see the text —
 * e.g. `\,` (an invisible thin space) survives preprocessMarkdown intact but
 * renders as a bare, visible "," once markdown-it has tokenized it. Letter-led
 * commands (`\int`, `\frac`, `\sqrt`, …) are unaffected — letters aren't in
 * CommonMark's escapable set — so this only needs to touch the backslash
 * itself, and only inside math spans (fenced ```math bodies are already
 * exempt: markdown-it's fence rule never applies inline escaping to them).
 * mathText.ts's preprocessLatex decodes the marker back to "\" as its first
 * step, before any command table runs.
 *
 * Also converts `\(...\)` → `$...$`. CommonMark treats `\(` / `\)` as escaped
 * punctuation and strips those backslashes during inline tokenization, so
 * leaving `\(...\)` in the preprocessed string makes splitInlineMath miss the
 * span entirely and the UI shows raw `(\frac{...})`. `$` is not escapable that
 * way, and splitInlineMath already handles `$...$`.
 */
function protectMathEscapes(content: string): string {
  return content.replace(
    /\$([^$\n]+?)\$|\\\(([\s\S]+?)\\\)/g,
    (_full: string, dollarBody: string | undefined, parenBody: string | undefined) => {
      const body = (dollarBody ?? parenBody ?? "").replace(
        MATH_ESCAPE_BACKSLASH_RE,
        PROTECTED_ESCAPE_MARKER,
      );
      return `$${body}$`;
    },
  );
}

/** GitHub callouts, block math, and HTML details → fenced blocks the app understands. */
export function preprocessMarkdown(content: string): string {
  let out = repairBrokenMarkdownLinks(content);
  out = repairCorruptedPriceTierMarkdown(out);
  out = normalizeVerificationBullets(out);
  out = normalizeImplicitMath(out);
  out = normalizeBoldInlineMath(out);
  // The model often wraps inline math in backticks (`` `$x^2 = 4$` ``), which
  // markdown renders as inline CODE → raw literal `$...$`. Un-wrap backtick-
  // wrapped `$...$` so it renders as math inline with the prose (in sync with
  // the text, no late fence pop-in).
  out = out.replace(/`(\$[^`\n]+?\$)`/g, "$1");

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

  const { text: blockMathInput, restore: restorePriceTiers } = shieldPriceTiers(out);
  let blockMathOut = blockMathInput.replace(BLOCK_MATH_RE, (_m, latex: string) => {
    return `\n\`\`\`math\n${latex.trim()}\n\`\`\`\n`;
  });
  blockMathOut = blockMathOut.replace(BLOCK_MATH_BRACKET_RE, (_m, latex: string) => {
    return `\n\`\`\`math\n${latex.trim()}\n\`\`\`\n`;
  });
  out = restorePriceTiers(blockMathOut);
  out = unwrapCorruptedMathFences(out);

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

  // Molecule formulas before math retag — otherwise bare `O=O` becomes ```math.
  out = retagMoleculeMathToSmiles(out);
  out = retagMathAndDiagramFences(out);

  out = unwrapNonCodeFences(out);

  out = protectMathEscapes(out);

  return out;
}

export function extractBlockquoteMeta(raw: string): {
  quote: string;
  author?: string;
} {
  return parseQuoteAttribution(raw);
}

/** Move $...$ out of **...** so emphasis nodes do not swallow math delimiters. */
export function normalizeBoldInlineMath(content: string): string {
  return content.replace(/\*\*((?:(?!\*\*).)+)\*\*/g, (full, inner: string) => {
    if (!/\$[^$\n]+?\$/.test(inner)) return full;
    const parts = splitInlineMath(inner);
    if (!parts.some((part) => part.type === "math")) return full;

    let out = "";
    for (const part of parts) {
      if (part.type === "math") {
        out += `$${part.value}$`;
        continue;
      }
      const lead = part.value.match(/^\s+/)?.[0] ?? "";
      const trail = part.value.match(/\s+$/)?.[0] ?? "";
      const core = part.value.trim();
      if (core) out += `${lead}**${core}**${trail}`;
      else out += part.value;
    }
    return out.trim() ? out : full;
  });
}

/** Split paragraph text into plain + inline math segments ($...$ or \\(...\\)). */
export function splitInlineMath(
  text: string,
): Array<{ type: "text" | "math"; value: string }> {
  const parts: Array<{ type: "text" | "math"; value: string }> = [];
  const pattern = /\$([^$\n]+?)\$|\\\(([\s\S]+?)\\\)/g;
  let last = 0;
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(text)) !== null) {
    if (match.index > last) {
      parts.push({ type: "text", value: text.slice(last, match.index) });
    }
    parts.push({ type: "math", value: (match[1] ?? match[2] ?? "").trim() });
    last = match.index + match[0].length;
  }
  if (last < text.length) {
    parts.push({ type: "text", value: text.slice(last) });
  }
  return parts.length ? parts : [{ type: "text", value: text }];
}
