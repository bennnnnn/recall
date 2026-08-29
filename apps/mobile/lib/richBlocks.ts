import { sanitizeEmailDraft } from "@/lib/emailDraftSanitize";
import { parseGeometrySpec } from "@/lib/geometryBlock";
import { parseGraphSpec } from "@/lib/graphBlock";

export type CalloutKind = "tip" | "note" | "warning" | "info" | "important";

export type EmailDraft = {
  to?: string;
  subject?: string;
  body: string;
};

export type ComparisonDraft = {
  leftTitle: string;
  rightTitle: string;
  left: string[];
  right: string[];
};

export type CollapsibleDraft = {
  title: string;
  body: string;
};

export type SocialPlatform = "twitter" | "linkedin" | "generic";

const CALLOUT_LANGS = new Set([
  "tip",
  "note",
  "warning",
  "info",
  "important",
  "callout",
]);
const SOCIAL_LANGS: Record<string, SocialPlatform> = {
  twitter: "twitter",
  tweet: "twitter",
  x: "twitter",
  linkedin: "linkedin",
  social: "generic",
};
const MESSAGE_LANGS = new Set(["sms", "message", "reply"]);
const QUOTE_LANGS = new Set(["quote", "blockquote"]);

// Which langs are structured now lives in lib/fenceRegistry.ts, alongside the
// other per-fence behaviour flags, so the lists cannot drift apart again.
export { isStructuredFenceLang } from "@/lib/fenceRegistry";

export function parseCalloutKind(lang: string): CalloutKind {
  const l = lang.trim().toLowerCase();
  if (l.startsWith("callout-")) {
    const kind = l.slice("callout-".length) as CalloutKind;
    if (
      kind === "tip" ||
      kind === "note" ||
      kind === "warning" ||
      kind === "info" ||
      kind === "important"
    ) {
      return kind;
    }
  }
  if (
    l === "tip" ||
    l === "note" ||
    l === "warning" ||
    l === "info" ||
    l === "important"
  )
    return l;
  return "note";
}

export function parseSocialPlatform(lang: string): SocialPlatform | null {
  return SOCIAL_LANGS[lang.trim().toLowerCase()] ?? null;
}

export function isMessageLang(lang: string): boolean {
  return MESSAGE_LANGS.has(lang.trim().toLowerCase());
}

export function parseEmailDraft(text: string): EmailDraft | null {
  const lines = text.split("\n");
  let to: string | undefined;
  let subject: string | undefined;
  const bodyLines: string[] = [];
  let inBody = false;

  for (const line of lines) {
    const toMatch = line.match(/^to:\s*(.+)$/i);
    const subjectMatch = line.match(/^subject:\s*(.+)$/i);
    if (!inBody && toMatch) {
      to = toMatch[1].trim();
      continue;
    }
    if (!inBody && subjectMatch) {
      subject = subjectMatch[1].trim();
      continue;
    }
    if (!inBody && line.trim() === "" && (to || subject)) {
      inBody = true;
      continue;
    }
    inBody = true;
    bodyLines.push(line);
  }

  const body = bodyLines.join("\n").trim();
  if (!to && !subject) return null;
  return sanitizeEmailDraft({ to, subject, body: body || text.trim() });
}

export function parseKeyValue(
  text: string,
): Array<{ key: string; value: string }> {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const idx = line.indexOf(":");
      if (idx <= 0) return { key: line, value: "" };
      return {
        key: line.slice(0, idx).trim(),
        value: line.slice(idx + 1).trim(),
      };
    });
}

export function parseSteps(text: string): string[] {
  const lines = text
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);
  return lines
    .map((line) =>
      line
        .replace(/^\d+[\).\]]\s*/, "")
        .replace(/^[-*]\s*/, "")
        .trim(),
    )
    .filter(Boolean);
}

export function parseComparison(text: string): ComparisonDraft | null {
  const lines = text.split("\n");
  let mode: "left" | "right" | null = null;
  let leftTitle = "Pros";
  let rightTitle = "Cons";
  const left: string[] = [];
  const right: string[] = [];

  for (const raw of lines) {
    const line = raw.trim();
    if (!line) continue;
    const leftHeading = line.match(
      /^(pros?|advantages?|option\s*a|left):\s*(.*)$/i,
    );
    const rightHeading = line.match(
      /^(cons?|disadvantages?|option\s*b|right):\s*(.*)$/i,
    );
    if (leftHeading) {
      mode = "left";
      if (leftHeading[2]) leftTitle = leftHeading[2].trim() || leftTitle;
      continue;
    }
    if (rightHeading) {
      mode = "right";
      if (rightHeading[2]) rightTitle = rightHeading[2].trim() || rightTitle;
      continue;
    }
    const item = line.replace(/^[-*]\s*/, "").trim();
    if (!item) continue;
    if (mode === "right") right.push(item);
    else left.push(item);
  }

  if (left.length === 0 && right.length === 0) return null;
  return { leftTitle, rightTitle, left, right };
}

export function parseCollapsible(lang: string, text: string): CollapsibleDraft {
  const l = lang.trim().toLowerCase();
  if (l === "details" || l === "collapse" || l === "summary") {
    const nl = text.indexOf("\n");
    if (nl === -1) return { title: text.trim() || "Details", body: "" };
    return {
      title: text.slice(0, nl).trim() || "Details",
      body: text.slice(nl + 1).trim(),
    };
  }
  return { title: "Details", body: text.trim() };
}

export function parseQuoteAttribution(text: string): {
  quote: string;
  author?: string;
} {
  const lines = text.split("\n").map((l) => l.replace(/^>\s?/, ""));
  const last = lines[lines.length - 1]?.trim() ?? "";
  const attrMatch = last.match(/^(?:—|--|-)\s*(.+)$/);
  if (attrMatch) {
    return {
      quote: lines.slice(0, -1).join("\n").trim(),
      author: attrMatch[1].trim(),
    };
  }
  const inline = splitTrailingAttribution(last);
  if (inline) {
    const prior = lines.slice(0, -1).join("\n").trim();
    return {
      quote: prior ? `${prior}\n${inline.quote}` : inline.quote,
      author: inline.author,
    };
  }
  return { quote: lines.join("\n").trim() };
}

const MAX_ATTR_AUTHOR_CHARS = 60;

function looksLikePersonName(name: string): boolean {
  if (name.length < 2 || name.length > MAX_ATTR_AUTHOR_CHARS) return false;
  const parts = name.split(" ");
  if (parts.length < 1 || parts.length > 6) return false;
  for (const part of parts) {
    if (!part) return false;
    const c0 = part.charCodeAt(0);
    if (c0 < 65 || c0 > 90) return false;
    for (let i = 0; i < part.length; i += 1) {
      const ch = part[i] ?? "";
      if (ch === "?" || ch === "!" || ch === ":" || ch === "/") return false;
    }
  }
  return true;
}

/** `quote. — Maya Angelou` → quote + author. Glued `be.—Shakespeare` stays intact. */
export function splitTrailingAttribution(
  text: string,
): { quote: string; author: string } | null {
  const t = text.trim();
  if (t.length < 12) return null;

  let i = t.length - 1;
  while (i >= 0 && (t[i] === " " || t[i] === "\t")) i -= 1;
  const authorEnd = i + 1;
  while (
    i >= 0 &&
    t[i] !== "-" &&
    t[i] !== "\u2014" &&
    t[i] !== "\u2013"
  ) {
    i -= 1;
  }
  if (i < 1) return null;
  const dashEnd = i;
  while (
    i >= 0 &&
    (t[i] === "-" || t[i] === "\u2014" || t[i] === "\u2013")
  ) {
    i -= 1;
  }
  const dashStart = i + 1;
  if (dashStart < 1) return null;
  const before = t[dashStart - 1];
  if (before !== " " && before !== "\t") return null;

  const quote = t.slice(0, dashStart).trim();
  const author = t.slice(dashEnd + 1, authorEnd).trim();
  if (quote.length < 8 || !looksLikePersonName(author)) return null;
  return { quote, author };
}

export function isStandaloneUrl(text: string): string | null {
  const t = text.trim();
  const match = t.match(/^https?:\/\/[^\s]+$/i);
  return match ? match[0] : null;
}

export type JsonRichFenceKind = "geometry" | "graph" | null;

/**
 * Detect whether a ```json (or untagged) fence body is actually a
 * geometry/graph spec, mistagged. The model is instructed to use
 * ```geometry / ```graph (never ```json) for diagrams but routinely
 * ignores that — without this, the fence falls through to a plain
 * syntax-highlighted JSON code block instead of the diagram it describes.
 */
export function detectJsonRichFenceKind(content: string): JsonRichFenceKind {
  if (parseGeometrySpec(content)) return "geometry";
  if (parseGraphSpec(content)) return "graph";
  return null;
}
