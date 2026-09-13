/** Copy vs speech conversion of assistant markdown (do not import printDocument). */

import { readFenceMarker } from "@/lib/mdFenceScan";
import {
  fenceIdForLang,
  isChartFenceLang,
  isControlFenceLang,
  isMathFenceLang,
  isVisualDiagramFenceLang,
} from "@/lib/fenceRegistry";
import { parseSimpleLatex, type MathSegment } from "@/lib/mathText";

function mapFenceRegions(
  text: string,
  onProse: (prose: string) => string,
  onFence: (lang: string, body: string) => string,
): string {
  const lines = text.split("\n");
  const out: string[] = [];
  let prose: string[] = [];
  let fence: { char: "`" | "~"; len: number; lang: string; body: string[] } | null = null;

  const flushProse = () => {
    if (prose.length === 0) return;
    const converted = onProse(prose.join("\n"));
    if (converted.length > 0) out.push(converted);
    prose = [];
  };

  const flushFence = () => {
    if (!fence) return;
    const converted = onFence(fence.lang, fence.body.join("\n"));
    if (converted.length > 0) out.push(converted);
    fence = null;
  };

  for (const line of lines) {
    const marker = readFenceMarker(line);
    if (fence) {
      if (
        marker &&
        marker.char === fence.char &&
        marker.len >= fence.len &&
        marker.info === ""
      ) {
        flushFence();
        continue;
      }
      fence.body.push(line);
      continue;
    }
    if (marker && !marker.info.includes("|")) {
      flushProse();
      fence = {
        char: marker.char,
        len: marker.len,
        lang: (marker.info.split(/\s/)[0] ?? "").toLowerCase(),
        body: [],
      };
      continue;
    }
    prose.push(line);
  }
  flushFence();
  flushProse();
  return out.join("\n");
}

function looksLikePipeRow(line: string): boolean {
  const trimmed = line.trim();
  return trimmed.startsWith("|") && trimmed.indexOf("|", 1) >= 0;
}

function pipeTablesToPlain(text: string): string {
  const lines = text.split("\n");
  const out: string[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i] ?? "";
    if (looksLikePipeRow(line)) {
      const rows: string[] = [];
      while (i < lines.length && looksLikePipeRow(lines[i] ?? "")) {
        const cells = (lines[i] ?? "")
          .split("|")
          .map((c) => c.trim())
          .filter(Boolean);
        if (!cells.every((c) => /^:?-+:?$/.test(c))) {
          rows.push(cells.join(" — "));
        }
        i += 1;
      }
      out.push(rows.join("\n"));
      continue;
    }
    out.push(line);
    i += 1;
  }
  return out.join("\n");
}

function unwrapDelimited(text: string, delim: string): string {
  let out = "";
  let i = 0;
  const n = delim.length;
  while (i < text.length) {
    if (text.startsWith(delim, i)) {
      const close = text.indexOf(delim, i + n);
      if (close < 0) {
        out += text.slice(i);
        break;
      }
      if (!text.slice(i, close).includes("\n") || n > 1) {
        out += text.slice(i + n, close);
        i = close + n;
        continue;
      }
    }
    out += text[i];
    i += 1;
  }
  return out;
}

/** Paired `_italic_` / `*italic*` only at word edges — never `user_id` or `a * b`. */
function unwrapWordEdgeMarker(text: string, marker: string): string {
  let out = "";
  let i = 0;
  while (i < text.length) {
    if (text[i] !== marker) {
      out += text[i];
      i += 1;
      continue;
    }
    const prev = i === 0 ? "" : text[i - 1] ?? "";
    const next = text[i + 1] ?? "";
    const openOk = !/[A-Za-z0-9]/.test(prev) && next !== "" && next !== marker && next !== " ";
    if (!openOk) {
      out += text[i];
      i += 1;
      continue;
    }
    const close = text.indexOf(marker, i + 1);
    if (close < 0 || text.slice(i, close).includes("\n")) {
      out += text[i];
      i += 1;
      continue;
    }
    const after = text[close + 1] ?? "";
    const inner = text.slice(i + 1, close);
    const closeOk = inner.length > 0 && inner[inner.length - 1] !== " " && !/[A-Za-z0-9]/.test(after);
    if (!closeOk) {
      out += text[i];
      i += 1;
      continue;
    }
    out += inner;
    i = close + 1;
  }
  return out;
}

function stripMarkdownChrome(text: string): string {
  let out = text.replace(/!\[[^\]]*\]\([^)]+\)/g, " ");
  out = out.replace(/\[([^\]]+)\]\(([^)]+)\)/g, "$1");
  out = out.replace(/^#{1,6}\s+/gm, "");
  out = out.replace(/^>\s?/gm, "");
  out = out.replace(/^(\s*)[-+]\s+/gm, "$1• ");
  // Whole-message Copy must preserve sequence/rank and nested indentation.
  // Removing `1.`, `2.`, `3.` turned copied procedures into unordered lines.
  out = out.replace(/^(\s*)(\d+)\.\s+/gm, "$1$2. ");
  out = unwrapDelimited(out, "**");
  out = unwrapDelimited(out, "__");
  out = unwrapDelimited(out, "~~");
  out = unwrapDelimited(out, "`");
  out = unwrapWordEdgeMarker(out, "_");
  out = unwrapWordEdgeMarker(out, "*");
  out = out.replace(/^(\s*)\*\s+/gm, "$1• ");
  return out;
}

function speakMath(latex: string): string {
  return latex
    .replace(/\\frac\{([^}]+)\}\{([^}]+)\}/g, "$1 over $2")
    .replace(/\\sqrt\{([^}]+)\}/g, "sqrt $1")
    .replace(/\\times/g, " times ")
    .replace(/\\cdot/g, " dot ")
    .replace(/\\pm/g, " plus or minus ")
    .replace(/[{}]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

/** Copy needs explicit grouping; visual fraction bars and radical overbars vanish. */
function copyMathSegments(segments: MathSegment[], depth = 0): string {
  const fractionSide = (side: MathSegment[]): string => {
    const text = copyMathSegments(side, depth + 1).trim();
    return side.length === 1 && side[0]?.type === "text"
      && /^(?:[+-]?\d+(?:\.\d+)?|\p{L})$/u.test(text)
      ? text : `(${text})`;
  };
  return segments.map((segment, index) => {
    switch (segment.type) {
      case "text": return segment.value;
      case "sup":
      case "sub": {
        const value = depth >= 12 ? segment.value : copyMathSegments(parseSimpleLatex(segment.value), depth + 1);
        return `${segment.type === "sup" ? "^" : "_"}${value.length === 1 ? value : `{${value}}`}`;
      }
      case "frac": {
        const fraction = `${fractionSide(segment.num)}/${fractionSide(segment.den)}`;
        const next = segments[index + 1];
        return next?.type === "sup" || next?.type === "sub" ? `(${fraction})` : fraction;
      }
      case "sqrt": {
        const index = segment.degree ? `[${copyMathSegments(parseSimpleLatex(segment.degree), depth + 1)}]` : "";
        return `√${index}(${copyMathSegments(segment.body, depth + 1)})`;
      }
    }
  }).join("");
}

/** Native script segment values flatten structure; keep the original formula
 * when those values cannot be serialized without losing grouping. */
function hasStructuredScript(latex: string): boolean {
  for (let i = 0; i < latex.length; i += 1) {
    if (latex[i] !== "^" && latex[i] !== "_") continue;
    let open = i + 1;
    while (/\s/.test(latex[open] ?? "") && open < latex.length) open += 1;
    if (latex[open] !== "{") continue;
    let depth = 1;
    let close = open + 1;
    for (; close < latex.length; close += 1) {
      if (latex[close] === "\\") { close += 1; continue; }
      if (latex[close] === "{") depth += 1;
      else if (latex[close] === "}") depth -= 1;
      if (depth === 0) break;
    }
    if (depth !== 0 || /\\(?:[dct]?frac|sqrt)\b|[_^]/.test(latex.slice(open + 1, close))) return true;
    i = close;
  }
  return false;
}

function copyMath(latex: string): string {
  if (hasStructuredScript(latex)) return latex.trim();
  return copyMathSegments(parseSimpleLatex(latex)).replace(/\$/g, "").trim();
}

function isMathDollarInner(inner: string): boolean {
  const t = inner.trim();
  if (!t) return false;
  if (/\\[a-zA-Z]/.test(t) || /[\^=_]/.test(t)) return true;
  if (/[=<>]/.test(t)) return true;
  if (/^[A-Za-z]$/.test(t)) return true;
  return /\d/.test(t) && /[+\-*/]/.test(t);
}

function rewriteInlineMath(text: string, convert: (latex: string) => string): string {
  let out = "";
  let i = 0;
  while (i < text.length) {
    if (text.startsWith("$$", i)) {
      const close = text.indexOf("$$", i + 2);
      if (close < 0) {
        out += text[i];
        i += 1;
        continue;
      }
      out += convert(text.slice(i + 2, close));
      i = close + 2;
      continue;
    }
    if (text[i] !== "$") {
      out += text[i];
      i += 1;
      continue;
    }
    const close = text.indexOf("$", i + 1);
    if (close < 0 || text.slice(i + 1, close).includes("\n")) {
      out += text[i];
      i += 1;
      continue;
    }
    const inner = text.slice(i + 1, close);
    if (isMathDollarInner(inner)) {
      out += convert(inner);
      i = close + 1;
      continue;
    }
    out += text[i];
    i += 1;
  }
  return out;
}

function convertProse(prose: string, mode: "copy" | "speech"): string {
  let text = pipeTablesToPlain(prose);
  text = stripMarkdownChrome(text);
  if (mode === "speech") text = rewriteInlineMath(text, speakMath);
  else text = rewriteInlineMath(text, copyMath);
  return text;
}

function convertFence(lang: string, body: string, mode: "copy" | "speech"): string {
  const trimmed = body.replace(/\n$/, "").trim();
  if (isControlFenceLang(lang)) return "";
  if (isChartFenceLang(lang)) return mode === "speech" ? "a chart" : "";
  if (isVisualDiagramFenceLang(lang)) return mode === "speech" ? "a diagram" : "";
  if (fenceIdForLang(lang) === "answer") {
    return mode === "speech" ? speakMath(trimmed) : copyMath(trimmed);
  }
  if (isMathFenceLang(lang)) {
    return mode === "speech" ? speakMath(trimmed) : copyMath(trimmed);
  }
  if (lang.startsWith("callout-")) return convertProse(trimmed, mode);
  return trimmed;
}

function convertMarkdown(markdown: string, mode: "copy" | "speech"): string {
  const walked = mapFenceRegions(
    markdown,
    (prose) => convertProse(prose, mode),
    (lang, body) => convertFence(lang, body, mode),
  );
  return walked.replace(/\n{3,}/g, "\n\n").trim();
}

/** Whole-message Copy: keep code and identifiers; flatten `$...$` math to readable text. */
export function markdownToCopyText(markdown: string): string {
  return convertMarkdown(markdown, "copy");
}

/** Read-aloud: speak prose and results; label visuals; skip control JSON. */
export function markdownToSpeechText(markdown: string): string {
  return convertMarkdown(markdown, "speech");
}

/** @deprecated Prefer markdownToSpeechText; kept as the TTS alias. */
export function markdownToPlainText(markdown: string): string {
  return markdownToSpeechText(markdown);
}
