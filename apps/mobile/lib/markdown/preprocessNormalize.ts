const DETAILS_HTML_RE =
  /<details>\s*<summary>([\s\S]*?)<\/summary>\s*([\s\S]*?)<\/details>/gim;

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

/**
 * Models sometimes put a list label and its value on separate lines:
 * `- **Chemical Formula**\n  : O₂`. The leading colon becomes a conspicuous
 * standalone glyph in React Native. Keep the intended two-line layout while
 * dropping only that decorative colon.
 */
export function stripBoldListLabelContinuationColons(content: string): string {
  const lines = content.split("\n");
  const out: string[] = [];
  let inFence = false;
  for (const originalLine of lines) {
    const trimmed = originalLine.trim();
    if (/^(?:```|~~~)/.test(trimmed)) {
      inFence = !inFence;
      out.push(originalLine);
      continue;
    }

    const previous = out[out.length - 1]?.trim() ?? "";
    const previousIsBoldListLabel =
      /^(?:[-*+]|\d+[.)])\s+\*\*[^*\n]+\*\*\s*$/.test(previous);
    if (!inFence && previousIsBoldListLabel) {
      out.push(originalLine.replace(/^(\s*):(?:\s+|$)/, "$1"));
      continue;
    }
    out.push(originalLine);
  }
  return out.join("\n");
}

/**
 * Models glue an ATX heading onto the previous sentence
 * (``$y=3x+4$: ### Explanation``). CommonMark only recognizes headings at
 * line start, so the hashes leak as literal ``###``. Break them out.
 */
export function breakMidlineAtxHeadings(content: string): string {
  const lines = content.split("\n");
  const out: string[] = [];
  let inFence = false;
  for (const line of lines) {
    const trimmed = line.trim();
    if (/^(?:```|~~~)/.test(trimmed)) {
      inFence = !inFence;
      out.push(line);
      continue;
    }
    if (inFence || !line.includes("#")) {
      out.push(line);
      continue;
    }
    const split = line.replace(/([^\n#])[ \t]*(#{1,6}[ \t]+\S)/g, "$1\n\n$2");
    if (split === line) {
      out.push(line);
    } else {
      out.push(...split.split("\n"));
    }
  }
  return out.join("\n");
}

export function convertDetailsBlocks(content: string): string {
  return content.replace(DETAILS_HTML_RE, (_m, title: string, body: string) => {
    return `\n\`\`\`details ${title.trim()}\n${body.trim()}\n\`\`\`\n`;
  });
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
export function retagVegaFences(src: string): string {
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
export function wrapBareVegaJson(src: string): string {
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
