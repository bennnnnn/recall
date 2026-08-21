import { retagMoleculeMathToSmiles } from "@/lib/chemistryFence";
import {
  retagMathAndDiagramFences,
  shouldRenderMathFenceInline,
  stripRedundantDollarWrap,
} from "@/lib/mathFenceRetag";
import { repairBrokenMarkdownLinks } from "@/lib/placesList";
import { normalizeImplicitMath, isMathLike } from "@/lib/normalizeImplicitMath";
import { isStructuredFenceLang } from "@/lib/richBlocks";
import {
  isAnswerLang,
  isExplicitCodeLang,
  looksLikeCode,
  looksLikeMathAnswer,
  shouldRenderAsPlainProseFence,
} from "@/lib/copyBlock";
import { isHtmlFenceLang, parseFenceLang } from "@/lib/codeHighlight";
import {
  PROTECTED_ESCAPE_MARKER,
  PROTECTED_MATH_STAR_MARKER,
  PROTECTED_MATH_UNDERSCORE_MARKER,
} from "@/lib/mathText";

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

/** Math/answer/graph/geometry fences that should be lifted out of list items. */
const LIFT_MATH_FENCE_LANG = /^(math|latex|tex|answer|graph|geometry)$/i;

/**
 * The model glues a fence opener to the end of a sentence
 * (`Multiply both sides by r: ```math` or `Here's the code: ```python`).
 * CommonMark only recognizes a fence at the start of a line, so the
 * backticks and the body paint as prose. Pull those openers onto their own
 * line before markdown-it runs. Handles ALL fence langs, not just math ones.
 */
export function breakAttachedMathFences(content: string): string {
  const lines = content.split("\n");
  const out: string[] = [];

  const openFence = (lang: string) => {
    if (out.length > 0 && out[out.length - 1] !== "") out.push("");
    out.push("```" + lang.toLowerCase());
  };

  const takeLang = (afterTicks: string): { lang: string; rest: string } | null => {
    let i = 0;
    // Read letters, digits, and hyphens — fence langs like "vega-lite",
    // "callout-note", and "molecule3d" contain hyphens/digits. Without
    // digits, "molecule3d" was split into lang "molecule" + body "3d".
    while (i < afterTicks.length && /[\w-]/.test(afterTicks[i]!)) i += 1;
    const lang = afterTicks.slice(0, i);
    // Accept any recognized fence lang: structured (math, graph, geometry,
    // mermaid, …), answer, or explicit code (python, javascript, …). This
    // lifts glued fence openers for ALL langs, not just math ones — the
    // model also glues code fences to prose ("Here's the code: ```python").
    const l = lang.toLowerCase();
    if (!isStructuredFenceLang(l) && !isAnswerLang(l) && !isExplicitCodeLang(l)) {
      return null;
    }
    return { lang, rest: afterTicks.slice(i).trim() };
  };

  const splitTrailingCloser = (rest: string): { body: string; closed: boolean } => {
    if (rest.endsWith("```")) {
      return { body: rest.slice(0, -3).trim(), closed: true };
    }
    return { body: rest, closed: false };
  };

  for (const line of lines) {
    const tick = line.indexOf("```");
    if (tick === -1) {
      out.push(line);
      continue;
    }
    const prefix = line.slice(0, tick);
    const parsed = takeLang(line.slice(tick + 3));
    if (!parsed) {
      out.push(line);
      continue;
    }
    const attached = prefix.trim().length > 0;
    const { body, closed } = splitTrailingCloser(parsed.rest);
    if (!attached && !body) {
      out.push(line);
      continue;
    }
    if (attached) out.push(prefix.trimEnd());
    openFence(parsed.lang);
    if (body) out.push(body);
    if (closed) {
      out.push("```");
      out.push("");
    }
  }
  return out.join("\n");
}

const MATHISH_TICK_INNER = /^[\dA-Za-z+\-*/^=().\s\\{}^_√±×÷·,]+$/;

function backtickInnerIsMath(inner: string): boolean {
  const t = inner.trim();
  if (!t) return false;
  if (/\$/.test(t) || /\\[a-zA-Z]+/.test(t)) return true;
  if (/\b[A-Za-z]{3,}\b/.test(t)) return false;
  if (isMathLike(t)) return true;
  return MATHISH_TICK_INNER.test(t) && /[\d=+\-*/^]/.test(t);
}

/**
 * Models wrap arithmetic in markdown backticks (`2+8=42`) or leave a stray
 * closer tick on the check line. Those paint as a literal ` on screen.
 * Leave real ``` fences and non-math inline code alone.
 */
export function unwrapProseMathBackticks(content: string): string {
  const lines = content.split("\n");
  const out: string[] = [];
  let inFence = false;
  for (const line of lines) {
    const trimmed = line.trim();
    if (/^```/.test(trimmed)) {
      inFence = !inFence;
      out.push(line);
      continue;
    }
    if (inFence) {
      out.push(line);
      continue;
    }
    let s = line.replace(/`(\$[^`\n]+?\$)`/g, "$1");
    s = s.replace(/`([^`\n]+)`/g, (full, inner: string) => {
      const t = String(inner).trim();
      if (!t) return "";
      if (!backtickInnerIsMath(t)) return full;
      if (t.startsWith("$") && t.endsWith("$")) return t;
      return `$${t}$`;
    });
    s = s.replace(/`+\s*$/, "");
    out.push(s);
  }
  return out.join("\n");
}

/**
 * CommonMark treats a ```math fence as indented code (raw backticks on screen)
 * when it sits inside a numbered list item. Pull math/answer fences to column 0
 * with a blank line before/after so they parse as real fences.
 */
export function liftMathFencesOutOfLists(content: string): string {
  const lines = content.split("\n");
  const out: string[] = [];
  let inFence: "math" | "other" | null = null;
  for (const line of lines) {
    const trimmed = line.trim();
    const open = trimmed.match(/^```([a-zA-Z][\w-]*)\s*$/);
    if (inFence == null) {
      if (open && LIFT_MATH_FENCE_LANG.test(open[1]!)) {
        if (out.length > 0 && out[out.length - 1] !== "") out.push("");
        out.push("```" + open[1]!.toLowerCase());
        inFence = "math";
        continue;
      }
      if (open) {
        inFence = "other";
        out.push(line);
        continue;
      }
      out.push(line);
      continue;
    }
    if (/^```$/.test(trimmed)) {
      out.push(inFence === "math" ? "```" : line);
      if (inFence === "math") out.push("");
      inFence = null;
      continue;
    }
    // When the fence opener was lifted to column 0, strip the original list
    // indent from body lines too — otherwise CommonMark treats 4+ space-
    // indented body lines as indented code blocks, not fence content.
    if (inFence === "math") {
      out.push(trimmed);
      continue;
    }
    out.push(line);
  }
  return out.join("\n");
}

const INLINE_MATH_FENCE_INFO = /^(math|latex|tex)?$/i;

function isFenceCloser(line: string, open: { char: "`" | "~"; len: number }): boolean {
  const m = readFenceMarker(line);
  return Boolean(m && m.char === open.char && m.len >= open.len && !m.info);
}

function appendInlineMath(out: string[], latex: string): void {
  const piece = `$${latex}$`;
  while (out.length > 0 && out[out.length - 1]!.trim() === "") out.pop();
  if (out.length > 0 && out[out.length - 1]!.trim() !== "") {
    const prev = out[out.length - 1]!;
    const gap = prev.endsWith(" ") ? "" : " ";
    out[out.length - 1] = prev.replace(/\s+$/, "") + gap + piece;
    return;
  }
  out.push(piece);
}

/**
 * Models put `$2+Y$` / `Y` in ```math (or an untagged fence). Those parse as
 * block cards — a gray box that splits the sentence. Fold short one-liners
 * back into `$...$`. Keep ```answer finals and multi-line display math.
 */
export function inlineShortMathFences(content: string): string {
  const lines = content.split("\n");
  const out: string[] = [];
  let i = 0;
  while (i < lines.length) {
    const open = readFenceMarker(lines[i]!);
    const lang = open?.info.split(/\s/)[0] ?? "";
    if (!open || !INLINE_MATH_FENCE_INFO.test(lang)) {
      out.push(lines[i]!);
      i += 1;
      continue;
    }
    const body: string[] = [];
    let j = i + 1;
    while (j < lines.length && !isFenceCloser(lines[j]!, open)) {
      body.push(lines[j]!);
      j += 1;
    }
    if (j >= lines.length) {
      out.push(lines[i]!);
      i += 1;
      continue;
    }
    const raw = body.join("\n").trim();
    const keepAnswer = isAnswerLang(lang) && looksLikeMathAnswer(raw);
    const keepCode = !lang && looksLikeCode(raw);
    if (keepAnswer || keepCode || !shouldRenderMathFenceInline(raw)) {
      for (let k = i; k <= j; k += 1) out.push(lines[k]!);
      i = j + 1;
      continue;
    }
    appendInlineMath(out, stripRedundantDollarWrap(raw));
    i = j + 1;
    while (i < lines.length && lines[i]!.trim() === "") i += 1;
    if (i < lines.length && isSafeInlineMathTail(lines[i]!.trim())) {
      const tail = lines[i]!.trim();
      const last = out[out.length - 1] ?? "";
      out[out.length - 1] = last + (last.endsWith(" ") ? "" : " ") + tail;
      i += 1;
    }
  }
  return out.join("\n");
}

/**
 * A line that is safe to merge onto the preceding inlined math fence —
 * starts with a punctuation character that continues the sentence (`?`, `!`,
 * `,`, `.`, `;`, `:`) but is NOT a structural markdown element (heading,
 * list item, image, table row, or blockquote).
 */
function isSafeInlineMathTail(t: string): boolean {
  if (!/^[?!,.;:]/.test(t)) return false;
  if (/^#{1,6}\s/.test(t)) return false; // heading
  if (/^[-*+]\s/.test(t)) return false; // unordered list item
  if (/^\d+\.\s/.test(t)) return false; // ordered list item
  if (/^!\[/.test(t)) return false; // image
  if (/^\|/.test(t)) return false; // table row
  if (/^>\s?/.test(t)) return false; // blockquote / callout
  return true;
}

function isPipeRow(line: string): boolean {
  const t = line.trim();
  return t.includes("|") && /^\|.+\|$/.test(t);
}

function isLoosePipeRow(line: string): boolean {
  const t = line.trim();
  if (!t.includes("|") || isDividerLine(t)) return false;
  const cells = splitPipesOutsideMath(t)
    .map((c) => c.trim())
    .filter((c) => c.length > 0);
  return cells.length >= 2;
}

/** GFM tables split on `|`; abs-bars inside `$...$` must not count as columns. */
function splitPipesOutsideMath(line: string): string[] {
  const cells: string[] = [];
  let buf = "";
  let inMath = false;
  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];
    if (ch === "$") {
      inMath = !inMath;
      buf += ch;
      continue;
    }
    if (ch === "|" && !inMath) {
      cells.push(buf);
      buf = "";
      continue;
    }
    buf += ch;
  }
  cells.push(buf);
  return cells;
}

function isTableRow(line: string): boolean {
  return isPipeRow(line) || isLoosePipeRow(line);
}

/** Lines the model uses instead of proper table rows: ---, ___, ===, etc. */
function isDividerLine(line: string): boolean {
  // Collapse whitespace first — avoid nested `(\s*[-–—_=*~]\s*){3,}` (js/redos).
  const compact = line.trim().replace(/\s+/g, "");
  return compact.length >= 3 && /^[-–—_=*~]+$/.test(compact);
}

/** CommonMark fence opener/closer: 3+ backticks or tildes, up to 3 leading spaces. */
function readFenceMarker(line: string): { char: "`" | "~"; len: number; info: string } | null {
  let i = 0;
  while (i < line.length && i < 3 && line[i] === " ") i += 1;
  const char = line[i];
  if (char !== "`" && char !== "~") return null;
  let len = 0;
  while (i < line.length && line[i] === char) {
    len += 1;
    i += 1;
  }
  if (len < 3) return null;
  return { char, len, info: line.slice(i).trim() };
}

/** `---` between two pipe rows is a fake separator; keep it as an hr / setext otherwise. */
function isTableDebrisDivider(prev: string | undefined, next: string | undefined): boolean {
  return Boolean(prev && next && isTableRow(prev) && isTableRow(next));
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
  let parts = splitPipesOutsideMath(t).map((c) => c.trim());
  if (parts[0] === "") parts = parts.slice(1);
  if (parts[parts.length - 1] === "") parts = parts.slice(0, -1);
  return `| ${parts.join(" | ")} |`;
}

function separatorForHeader(headerLine: string): string {
  const strict = toStrictPipeRow(headerLine);
  const cols = splitPipesOutsideMath(strict).filter((c) => c.trim().length > 0);
  return `|${cols.map(() => " --- ").join("|")}|`;
}

function isGhostTableRow(line: string): boolean {
  if (!isTableRow(line)) return false;
  const strict = toStrictPipeRow(line);
  const cells = splitPipesOutsideMath(strict)
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
  let openFence: { char: "`" | "~"; len: number } | null = null;

  const flushTable = () => {
    if (tableBuffer.length >= 2) {
      fixed.push(...finalizePipeTable(tableBuffer));
    } else {
      fixed.push(...tableBuffer);
    }
    tableBuffer = [];
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const marker = readFenceMarker(line);

    if (openFence) {
      if (
        marker &&
        marker.char === openFence.char &&
        marker.len >= openFence.len &&
        marker.info === ""
      ) {
        openFence = null;
      }
      fixed.push(line);
      continue;
    }

    if (marker) {
      flushTable();
      openFence = { char: marker.char, len: marker.len };
      fixed.push(line);
      continue;
    }

    if (isDividerLine(line) && isTableDebrisDivider(lines[i - 1], lines[i + 1])) {
      continue;
    }

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

/**
 * Check lines like `For $x = 2$: $2^2 + 2 = 6$` (or `For F = 0: 0 + 3 = 3 ✓`)
 * must not cram the substitution onto the label line. Split after the colon.
 */
export function layoutCheckVerificationLines(content: string): string {
  let out = content.replace(
    /\$([^$\n]*?=\s*-?\d+)\s*:\s*([^$\n]+)\$/g,
    (_m, label: string, formula: string) => `$${label.trim()}$: $${formula.trim()}$`,
  );
  out = out.replace(/\$:\s*/g, "$: ");
  return out.split("\n").map(splitPackedCheckLine).join("\n");
}

/**
 * A line that is just ":" (a stranded colon) renders as a lone "two dots"
 * on its own line — the model put it on a separate line after a bold step
 * header (``**Multiply**\n:\n$3 \times 2 = 6$``). Merge it onto the previous
 * line so it renders inline (``**Multiply**:``) instead of stranded.
 *
 * Also handles stranded `;` (same pattern — the model puts the semicolon
 * on its own line after a step header or label).
 */
export function mergeStrandedColons(content: string): string {
  const lines = content.split("\n");
  const out: string[] = [];
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i]!;
    const trimmed = line.trim();
    if (trimmed === ":" || trimmed === ";") {
      if (out.length > 0) {
        const prev = out[out.length - 1]!;
        const prevTrimmed = prev.trim();
        // Don't glue punctuation onto a fence closer, table row, or heading.
        if (
          prevTrimmed.startsWith("```") ||
          prevTrimmed.startsWith("|") ||
          /^#{1,6}\s/.test(prevTrimmed)
        ) {
          out.push(line);
        } else {
          out[out.length - 1] = prev.replace(/\s*$/, "") + trimmed;
        }
      } else {
        out.push(line);
      }
    } else {
      out.push(line);
    }
  }
  return out.join("\n");
}

function splitPackedCheckLine(line: string): string {
  const colon = indexOfCheckLabelColon(line);
  if (colon < 0) return line;
  const after = line.slice(colon + 1).trim();
  if (!after || !looksLikeCheckComputation(after)) return line;
  const before = line.slice(0, colon + 1).trimEnd();
  return `${before}\n  ${after}`;
}

/** Colon that closes `For x = 2:` / `For $F = 0$:` — not "for example:". */
function indexOfCheckLabelColon(line: string): number {
  const lower = line.toLowerCase();
  const forAt = lower.indexOf("for ");
  if (forAt < 0) return -1;
  const colon = line.indexOf(":", forAt + 4);
  if (colon < 0) return -1;
  const label = line.slice(forAt, colon);
  if (!label.includes("=")) return -1;
  return colon;
}

function looksLikeCheckComputation(s: string): boolean {
  if (s.length < 3) return false;
  return /[\d$=+\-]/.test(s);
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
 *
 * Bare `_` and `*` inside the same spans are swapped for PUA markers so
 * markdown-it's emphasis tokenizer cannot turn `$x_1 * y_2$` into nested
 * em/strong. mathText.ts restores them before parsing subscripts.
 */
function protectMathEscapes(content: string): string {
  return content.replace(
    /\$([^$\n]+?)\$|\\\(([\s\S]+?)\\\)/g,
    (_full: string, dollarBody: string | undefined, parenBody: string | undefined) => {
      const body = (dollarBody ?? parenBody ?? "")
        // Protect the LaTeX row separator "\\" (TWO backslashes) before the
        // single-backslash rule below runs. markdown-it treats a trailing
        // "\\" as a hard line break and silently drops both backslashes
        // during inline tokenization, collapsing every row of an inline
        // `\begin{matrix}…\\…\end{matrix}` into one run. split/join on the
        // two-backslash literal is unambiguous — it never touches the single
        // backslash of a command like "\frac".
        .split("\\\\")
        .join(`${PROTECTED_ESCAPE_MARKER}${PROTECTED_ESCAPE_MARKER}`)
        .replace(MATH_ESCAPE_BACKSLASH_RE, PROTECTED_ESCAPE_MARKER)
        .replace(/_/g, PROTECTED_MATH_UNDERSCORE_MARKER)
        .replace(/\*/g, PROTECTED_MATH_STAR_MARKER);
      return `$${body}$`;
    },
  );
}

/** GitHub callouts, block math, and HTML details → fenced blocks the app understands. */
const VEGA_FENCE_LANGS = new Set(["", "json", "vega", "vega-lite", "chart", "plot"]);
const VEGA_SCHEMA_MARKER = '"$schema"';
const VEGA_SCHEMA_HOST = "vega.github.io/schema/";

function fenceBodyLooksLikeVega(body: string): boolean {
  return (
    body.includes(VEGA_SCHEMA_MARKER) &&
    body.includes(VEGA_SCHEMA_HOST) &&
    body.includes("{") &&
    body.includes("}")
  );
}

/** Retag ```json/vega… fences that hold Vega specs — linear fence walk, no nested regex. */
function retagVegaFences(src: string): string {
  let out = "";
  let i = 0;
  while (i < src.length) {
    const open = src.indexOf("```", i);
    if (open === -1) {
      out += src.slice(i);
      break;
    }
    out += src.slice(i, open);
    const afterOpen = open + 3;
    const nl = src.indexOf("\n", afterOpen);
    if (nl === -1) {
      out += src.slice(open);
      break;
    }
    const lang = src.slice(afterOpen, nl).trim().toLowerCase();
    const close = src.indexOf("```", nl + 1);
    if (close === -1) {
      out += src.slice(open);
      break;
    }
    const body = src.slice(nl + 1, close);
    if (VEGA_FENCE_LANGS.has(lang) && fenceBodyLooksLikeVega(body) && lang !== "vega-lite") {
      out += "```vega-lite\n" + body.trim() + "\n```";
    } else {
      out += src.slice(open, close + 3);
    }
    i = close + 3;
  }
  return out;
}

/**
 * Wrap bare Vega-Lite JSON objects (not already fenced) so ChartBlock can render them.
 * Scans for `{` + `"$schema"` + vega host, then walks braces — no `[\s\S]*?` pump.
 */
function wrapBareVegaJson(src: string): string {
  let out = "";
  let i = 0;
  while (i < src.length) {
    const start = src.indexOf("{", i);
    if (start === -1) {
      out += src.slice(i);
      break;
    }
    const atBoundary = start === 0 || (start >= 2 && src.slice(start - 2, start) === "\n\n");
    if (!atBoundary) {
      out += src.slice(i, start + 1);
      i = start + 1;
      continue;
    }
    // Inside an open ``` fence? leave alone (retagVegaFences already handled).
    let fenceMarks = 0;
    for (let f = src.indexOf("```"); f !== -1 && f < start; f = src.indexOf("```", f + 3)) {
      fenceMarks += 1;
    }
    if (fenceMarks % 2 === 1) {
      out += src.slice(i, start + 1);
      i = start + 1;
      continue;
    }
    let k = start + 1;
    while (k < src.length && (src[k] === " " || src[k] === "\t" || src[k] === "\n" || src[k] === "\r")) {
      k += 1;
    }
    if (!src.startsWith(VEGA_SCHEMA_MARKER, k)) {
      out += src.slice(i, start + 1);
      i = start + 1;
      continue;
    }
    const hostAt = src.indexOf(VEGA_SCHEMA_HOST, k);
    if (hostAt === -1 || hostAt - k > 120) {
      out += src.slice(i, start + 1);
      i = start + 1;
      continue;
    }
    let depth = 0;
    let end = -1;
    const scanLimit = Math.min(src.length, start + 100_000);
    for (let j = start; j < scanLimit; j += 1) {
      const ch = src[j];
      if (ch === "{") depth += 1;
      else if (ch === "}") {
        depth -= 1;
        if (depth === 0) {
          end = j;
          break;
        }
      }
    }
    // Prior regex required a newline immediately before the closing `}`.
    if (end === -1 || end === 0 || src[end - 1] !== "\n") {
      out += src.slice(i, start + 1);
      i = start + 1;
      continue;
    }
    const body = src.slice(start, end + 1);
    if (!fenceBodyLooksLikeVega(body)) {
      out += src.slice(i, start + 1);
      i = start + 1;
      continue;
    }
    out += src.slice(i, start);
    out += `\n\n\`\`\`vega-lite\n${body.trim()}\n\`\`\`\n\n`;
    i = end + 1;
  }
  return out;
}

export function preprocessMarkdown(
  content: string,
  mathFormat?: (expr: string) => string,
): string {
  let out = repairBrokenMarkdownLinks(content);
  out = repairCorruptedPriceTierMarkdown(out);
  out = normalizeVerificationBullets(out);
  out = normalizeImplicitMath(out, mathFormat);
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

  // Re-tag Vega fences / bare JSON with linear scans (no nested [\s\S]*? ReDoS).
  out = retagVegaFences(out);
  out = wrapBareVegaJson(out);

  // Molecule formulas before math retag — otherwise bare `O=O` becomes ```math.
  out = retagMoleculeMathToSmiles(out);
  out = retagMathAndDiagramFences(out);

  out = unwrapNonCodeFences(out);

  out = protectMathEscapes(out);
  out = layoutCheckVerificationLines(out);
  out = mergeStrandedColons(out);
  out = breakAttachedMathFences(out);

  out = protectMathEscapes(out);
  out = layoutCheckVerificationLines(out);
  out = mergeStrandedColons(out);
  out = breakAttachedMathFences(out);
  out = liftMathFencesOutOfLists(out);
  out = inlineShortMathFences(out);
  out = unwrapProseMathBackticks(out);

  return out;
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
