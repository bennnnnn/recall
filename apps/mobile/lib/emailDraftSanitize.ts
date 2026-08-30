/** Strip model form-slots from a parsed email draft so copy/Gmail are send-ready. */

export type EmailDraftFields = {
  to?: string;
  subject?: string;
  body: string;
};

const FORM_SLOT_KEYS = [
  "name",
  "email",
  "address",
  "placeholder",
  "recipient",
  "manager",
  "boss",
  "subject",
  "company",
  "title",
  "date",
  "tbd",
];

const LONELY_GREETINGS = ["Hi", "Hello", "Hey", "Dear"];

function isDigitsOnly(s: string): boolean {
  if (!s) return false;
  for (let i = 0; i < s.length; i++) {
    const c = s.charCodeAt(i);
    if (c < 48 || c > 57) return false;
  }
  return true;
}

function isWordChar(ch: string | undefined): boolean {
  if (!ch) return false;
  const c = ch.charCodeAt(0);
  return (c >= 97 && c <= 122) || (c >= 48 && c <= 57);
}

function containsWord(haystack: string, word: string): boolean {
  let from = 0;
  while (from <= haystack.length - word.length) {
    const idx = haystack.indexOf(word, from);
    if (idx < 0) return false;
    const before = idx === 0 ? undefined : haystack[idx - 1];
    const after = haystack[idx + word.length];
    if (!isWordChar(before) && !isWordChar(after)) return true;
    from = idx + 1;
  }
  return false;
}

/** `[Your Name]` / `[Manager's Email Address]` — not `[1]` or markdown links. */
function isFormSlot(inner: string): boolean {
  const s = inner.trim().toLowerCase();
  if (!s || s.length > 48) return false;
  if (isDigitsOnly(s)) return false;
  if (s.includes("http") || s.includes("(")) return false;
  for (const key of FORM_SLOT_KEYS) {
    if (containsWord(s, key)) return true;
  }
  return false;
}

function stripFormSlots(text: string): string {
  let out = "";
  let i = 0;
  while (i < text.length) {
    const open = text.indexOf("[", i);
    if (open < 0) {
      out += text.slice(i);
      break;
    }
    const close = text.indexOf("]", open + 1);
    if (close < 0) {
      out += text.slice(i);
      break;
    }
    const inner = text.slice(open + 1, close);
    if (isFormSlot(inner)) {
      out += text.slice(i, open);
      i = close + 1;
    } else {
      out += text.slice(i, close + 1);
      i = close + 1;
    }
  }
  return collapsePlaceholderGaps(out);
}

function collapsePlaceholderGaps(text: string): string {
  const lines = text.split("\n");
  const cleaned: string[] = [];
  for (const line of lines) {
    let s = line;
    while (s.includes(" -  - ") || s.includes(" - - ")) {
      s = s.replace(" -  - ", " - ").replace(" - - ", " - ");
    }
    let compact = "";
    let space = false;
    for (let i = 0; i < s.length; i++) {
      const ch = s[i];
      if (ch === " " || ch === "\t") {
        if (!space) compact += " ";
        space = true;
      } else {
        compact += ch;
        space = false;
      }
    }
    cleaned.push(compact.trimEnd());
  }
  return cleaned.join("\n").trim();
}

function looksLikeEmailAddress(value: string): boolean {
  const at = value.indexOf("@");
  if (at <= 0) return false;
  const dot = value.indexOf(".", at + 1);
  return dot > at + 1 && dot < value.length - 1 && !value.includes("[");
}

function hasFormSlot(value: string): boolean {
  let i = 0;
  while (i < value.length) {
    const open = value.indexOf("[", i);
    if (open < 0) return false;
    const close = value.indexOf("]", open + 1);
    if (close < 0) return false;
    if (isFormSlot(value.slice(open + 1, close))) return true;
    i = close + 1;
  }
  return false;
}

function isPlaceholderAddress(value: string): boolean {
  const v = value.trim();
  if (!v) return true;
  if (looksLikeEmailAddress(v) && !hasFormSlot(v)) return false;
  if (hasFormSlot(v)) return true;
  const lower = v.toLowerCase();
  if (lower.includes("email address") || lower.includes("placeholder")) return true;
  if (lower === "email" || lower === "recipient" || lower === "name") return true;
  return lower.endsWith("'s name") || lower.endsWith("'s email");
}

function tidyLonelyGreeting(body: string): string {
  const nl = body.indexOf("\n");
  const firstRaw = nl < 0 ? body : body.slice(0, nl);
  const rest = nl < 0 ? "" : body.slice(nl);
  let first = firstRaw.trim();
  while (first.endsWith(",") || first.endsWith(":")) {
    first = first.slice(0, -1).trim();
  }
  const lower = first.toLowerCase();
  for (const g of LONELY_GREETINGS) {
    if (lower === g.toLowerCase()) return `${g},${rest}`;
  }
  return body;
}

export function stripDraftFormSlots(text: string): string {
  return stripFormSlots(text);
}

export function sanitizeEmailDraft(draft: EmailDraftFields): EmailDraftFields {
  const toRaw = draft.to?.trim() ?? "";
  const to = toRaw && !isPlaceholderAddress(toRaw) ? toRaw : undefined;
  const subjectRaw = draft.subject?.trim() ? stripFormSlots(draft.subject) : "";
  const subject =
    subjectRaw && !isPlaceholderAddress(subjectRaw) ? subjectRaw : undefined;
  const body = tidyLonelyGreeting(stripFormSlots(draft.body));
  return {
    ...(to ? { to } : {}),
    ...(subject ? { subject } : {}),
    body,
  };
}
