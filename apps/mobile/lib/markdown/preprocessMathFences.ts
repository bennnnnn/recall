import {
  isAnswerLang,
  isExplicitCodeLang,
  looksLikeCode,
  looksLikeMathAnswer,
} from "@/lib/copyBlock";
import { shouldLiftFenceOutOfList } from "@/lib/fenceRegistry";
import { isLoosePipeRow, isTableRow } from "@/lib/markdown/preprocessTables";
import {
  closeInterruptedMathFences,
  isMathFenceInterruptLine,
  shouldInlineMathFenceOnBareListMarker,
  shouldRenderMathFenceInline,
  stripRedundantDollarWrap,
} from "@/lib/math/fenceRetag";
import { isMathLike } from "@/lib/math/normalizeImplicit";
import { readFenceMarker, readFenceMarkerLoose } from "@/lib/mdFenceScan";
import { isStructuredFenceLang } from "@/lib/richBlocks";

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
    while (i < afterTicks.length && /[ \t]/.test(afterTicks[i]!)) i += 1;
    const start = i;
    // Read letters, digits, and hyphens — fence langs like "vega-lite",
    // "callout-note", and "molecule3d" contain hyphens/digits. Without
    // digits, "molecule3d" was split into lang "molecule" + body "3d".
    while (i < afterTicks.length && /[\w-]/.test(afterTicks[i]!)) i += 1;
    const lang = afterTicks.slice(start, i);
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
    const tick = line.search(/`{3,}/);
    if (tick === -1) {
      out.push(line);
      continue;
    }
    let tickLen = 0;
    while (line[tick + tickLen] === "`") tickLen += 1;
    const prefix = line.slice(0, tick);
    const parsed = takeLang(line.slice(tick + tickLen));
    if (!parsed) {
      out.push(line);
      continue;
    }
    const attached = prefix.trim().length > 0;
    // A table cell that starts ```python must NOT become a real fence —
    // CommonMark then swallows the rest of the comparison (live: Python vs
    // Java "Use Cases" grid rendered inside a python code block).
    if (attached && (isTableRow(prefix) || isLoosePipeRow(prefix))) {
      out.push(line);
      continue;
    }
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
      if (open && shouldLiftFenceOutOfList(open[1]!)) {
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

/**
 * CommonMark treats 4+ space (or tab) indented lines as a code block.
 * After an unclosed ```math, the next `2. **Simplify:**` often lands in
 * that indent — a gray Prism card of markdown source. Pull those steps
 * (and only those) back to column 0. Real fenced bodies are left alone.
 */
export function dedentMisindentedMarkdownSteps(content: string): string {
  const lines = content.split("\n");
  const out: string[] = [];
  let open: { char: "`" | "~"; len: number } | null = null;
  for (const line of lines) {
    if (open) {
      out.push(line);
      const closer = readFenceMarkerLoose(line);
      if (
        closer &&
        closer.char === open.char &&
        closer.len >= open.len &&
        closer.info === ""
      ) {
        open = null;
      }
      continue;
    }
    const marker = readFenceMarkerLoose(line);
    if (marker && !marker.info.includes("|")) {
      open = { char: marker.char, len: marker.len };
      out.push(line);
      continue;
    }
    if (/^(?:[ \t]{4,}|\t+)/.test(line) && isMathFenceInterruptLine(line)) {
      out.push(line.trimStart());
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
    const prev = out[out.length - 1]!.replace(/\s+$/, "");
    // Always a space after a list marker (`- $eq$`). Dropping it when the
    // line already ended in whitespace produced `-$eq$`, which CommonMark
    // does not treat as a list item.
    out[out.length - 1] = `${prev} ${piece}`;
    return;
  }
  out.push(piece);
}

/** `-` / `1.` with no body — the empty bullet a following ```math used to hide. */
function isBareListMarkerLine(line: string): boolean {
  return /^\s*(?:[-*•]|\d+[.)])\s*$/.test(line);
}

function lastNonemptyLine(lines: string[]): string | undefined {
  for (let i = lines.length - 1; i >= 0; i -= 1) {
    if (lines[i]!.trim() !== "") return lines[i];
  }
  return undefined;
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
    const host = lastNonemptyLine(out);
    const listInline =
      host != null &&
      isBareListMarkerLine(host) &&
      shouldInlineMathFenceOnBareListMarker(raw);
    if (
      keepAnswer ||
      keepCode ||
      !(listInline || shouldRenderMathFenceInline(raw))
    ) {
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

export { closeInterruptedMathFences };
