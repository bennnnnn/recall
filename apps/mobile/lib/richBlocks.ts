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
const STRUCTURED_LANGS = new Set([
  "email",
  "compare",
  "comparison",
  "pros",
  "kv",
  "keyvalue",
  "fields",
  "steps",
  "step",
  "details",
  "collapse",
  "summary",
  "math",
  "clock",
  "time",
  // Diagram / chart / visualization fences
  "mermaid",
  "chart",
  "vega",
  "vega-lite",
  "plot",
  "geometry",
  "graph",
  ...CALLOUT_LANGS,
  ...Object.keys(SOCIAL_LANGS),
  ...MESSAGE_LANGS,
]);

export function isStructuredFenceLang(lang: string): boolean {
  const l = lang.trim().toLowerCase();
  if (STRUCTURED_LANGS.has(l)) return true;
  return l.startsWith("callout-");
}

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
  return { to, subject, body: body || text.trim() };
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
  return { quote: lines.join("\n").trim() };
}

export function isStandaloneUrl(text: string): string | null {
  const t = text.trim();
  const match = t.match(/^https?:\/\/[^\s]+$/i);
  return match ? match[0] : null;
}
