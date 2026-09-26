import { splitTrailingAttribution } from "@/lib/richBlocks";

// Title uses horizontal whitespace only; body lines are `>[^\n]*` (no ReDoS).
const CALLOUT_RE =
  /^>[ \t]*\[!(\w+)\][ \t]*([^\n]*)\n((?:>[^\n]*(?:\n|$))*)/gim;
/** Markdown `> Tip:` / `> Warning:` — same cards as `> [!TIP]`, no custom fence. */
const CALLOUT_LABEL_LINE =
  /^>[ \t]*(Tip|Note|Warning|Important|Info)[ \t]*:[ \t]*(.*)$/i;

export function promoteCalloutBlockquotes(content: string): string {
  const lines = content.split("\n");
  const out: string[] = [];
  let i = 0;
  while (i < lines.length) {
    const match = CALLOUT_LABEL_LINE.exec(lines[i] ?? "");
    if (!match) {
      out.push(lines[i] ?? "");
      i += 1;
      continue;
    }
    const kind = (match[1] ?? "").trim().toLowerCase();
    const body: string[] = [];
    const first = (match[2] ?? "").trim();
    if (first) body.push(first);
    i += 1;
    while (i < lines.length) {
      const line = lines[i] ?? "";
      if (!line.startsWith(">")) break;
      if (CALLOUT_LABEL_LINE.test(line)) break;
      body.push(line.replace(/^>\s?/, ""));
      i += 1;
    }
    out.push(`> [!${kind}]`);
    for (const line of body) out.push(`> ${line}`);
    out.push("");
  }
  return out.join("\n");
}

const MIN_PROMOTED_QUOTE_CHARS = 24;
const MAX_PROMOTED_AUTHOR_CHARS = 60;

function collapseWs(s: string): string {
  let out = "";
  let prevSpace = false;
  for (let i = 0; i < s.length; i += 1) {
    const c = s[i] ?? "";
    const space = c === " " || c === "\n" || c === "\t" || c === "\r";
    if (space) {
      if (!prevSpace && out.length > 0) {
        out += " ";
        prevSpace = true;
      }
    } else {
      out += c;
      prevSpace = false;
    }
  }
  return out.trim();
}

function unwrapOuterEmphasis(text: string): string {
  let t = text.trim();
  if (t.length >= 4 && t.startsWith("**") && t.endsWith("**")) {
    t = t.slice(2, -2).trim();
  }
  if (t.length >= 2) {
    const a = t[0];
    const b = t[t.length - 1];
    if ((a === "*" && b === "*") || (a === "_" && b === "_")) {
      t = t.slice(1, -1).trim();
    }
  }
  return t;
}

function isQuoteOpen(ch: string): boolean {
  return ch === '"' || ch === "\u201C";
}

function isQuoteClose(ch: string): boolean {
  return ch === '"' || ch === "\u201D";
}

function isAttrDash(ch: string): boolean {
  return ch === "-" || ch === "\u2014" || ch === "\u2013";
}

function looksLikeAuthor(name: string): boolean {
  if (name.length < 2 || name.length > MAX_PROMOTED_AUTHOR_CHARS) return false;
  const c0 = name.charCodeAt(0);
  if (!((c0 >= 65 && c0 <= 90) || (c0 >= 97 && c0 <= 122))) return false;
  for (let i = 0; i < name.length; i += 1) {
    const ch = name[i] ?? "";
    if (ch === "?" || ch === "!" || ch === ":" || ch === "/") return false;
  }
  return true;
}

/** `"Quote body." - Author` → a `>` blockquote with attribution on its own line. */
export function quotedAttributionToBlockquote(raw: string): string | null {
  const t = unwrapOuterEmphasis(collapseWs(raw));
  if (t.length < MIN_PROMOTED_QUOTE_CHARS + 4) return null;
  if (t.startsWith(">") || t.startsWith("#") || t.startsWith("|")) return null;
  if (t.startsWith("- ") || t.startsWith("* ") || t.startsWith("```")) return null;
  if (!isQuoteOpen(t[0] ?? "")) return null;

  let close = -1;
  for (let i = t.length - 1; i > 0; i -= 1) {
    if (isQuoteClose(t[i] ?? "")) {
      close = i;
      break;
    }
  }
  if (close <= 1) return null;

  const quote = t.slice(1, close).trim();
  if (quote.length < MIN_PROMOTED_QUOTE_CHARS) return null;

  let rest = t.slice(close + 1).trim();
  if (!rest || !isAttrDash(rest[0] ?? "")) return null;
  rest = rest.slice(1).trim();
  if (!looksLikeAuthor(rest)) return null;

  return `> ${quote}\n>\n> — ${rest}`;
}

/** Promote standalone `"…" - Author` paragraphs into quote-card blockquotes. */
export function promoteQuotedAttributions(content: string): string {
  const lines = content.split("\n");
  const out: string[] = [];
  let i = 0;
  let inFence = false;
  while (i < lines.length) {
    const line = lines[i] ?? "";
    const trimmed = line.trimStart();
    if (trimmed.startsWith("```")) {
      inFence = !inFence;
      out.push(line);
      i += 1;
      continue;
    }
    if (inFence || trimmed === "") {
      out.push(line);
      i += 1;
      continue;
    }
    const para: string[] = [];
    while (i < lines.length) {
      const next = lines[i] ?? "";
      if (next.trim() === "") break;
      if (next.trimStart().startsWith("```")) break;
      para.push(next);
      i += 1;
    }
    const promoted = quotedAttributionToBlockquote(para.join(" "));
    if (promoted) {
      out.push(promoted);
    } else {
      out.push(...para);
    }
  }
  return out.join("\n");
}

/** `> quote. — Author` → attribution on its own blockquote line for QuoteBlock. */
export function splitBlockquoteInlineAttribution(content: string): string {
  const lines = content.split("\n");
  const out: string[] = [];
  let inFence = false;
  for (const line of lines) {
    const trimmed = line.trimStart();
    if (trimmed.startsWith("```")) {
      inFence = !inFence;
      out.push(line);
      continue;
    }
    if (inFence || !trimmed.startsWith(">")) {
      out.push(line);
      continue;
    }
    let prefixEnd = 0;
    while (prefixEnd < line.length && (line[prefixEnd] === " " || line[prefixEnd] === "\t")) {
      prefixEnd += 1;
    }
    prefixEnd += 1; // '>'
    if (line[prefixEnd] === " ") prefixEnd += 1;
    const body = line.slice(prefixEnd);
    if (body.startsWith("[!")) {
      out.push(line);
      continue;
    }
    const split = splitTrailingAttribution(body);
    if (!split) {
      out.push(line);
      continue;
    }
    out.push(`> ${split.quote}`);
    out.push(`>`);
    out.push(`> — ${split.author}`);
  }
  return out.join("\n");
}

export function convertCalloutBlocks(content: string): string {
  return content.replace(
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
}
