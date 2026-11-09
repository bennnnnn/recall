import { parseUserMessageContent } from "@/lib/messageAttachments";

type ChatTitleDisplayOptions = {
  /** True while waiting for auto-generated title after first exchange. */
  generating?: boolean;
};

/** Each quote mark's kind; any two marks of one kind pair, so every language's style does. */
const QUOTE_KIND: Readonly<Record<string, string>> = {
  '"': "double", "“": "double", "”": "double", "„": "double", "‟": "double",
  "'": "single", "‘": "single", "’": "single", "‚": "single", "‛": "single",
  "«": "angle", "»": "angle", "‹": "single angle", "›": "single angle",
};
/** Marks that only open (`„Bob“`, `«Bob»`, `‚Bob‘`) and marks that only close (`“Bob”`). */
const OPENS_ONLY = new Set(["„", "‚", "«", "‹"]);
const CLOSES_ONLY = new Set(["”", "’", "»", "›"]);
/** A mark between two of these is an apostrophe (Bob's), not a quote. */
const APOSTROPHES = new Set(["'", "’"]);
const OPEN_BEFORE = /^(?:\s|[([{])?$/u;
const TITLE_TRAIL_PUNCT = new Set([".", "!", "?", ",", ";", ":"]);
const WORD_CHAR = /[\p{L}\p{N}]/u;

/**
 * Each quote mark's partner, both ways. A mark that may open or close (`"`, `“`, `‘`) opens
 * at the start, after a space, a bracket or a mark that just opened; otherwise it closes the
 * nearest open mark of its kind (German `„Bob“` closes with `“`), and with none open it opens
 * before a word (`Re:"Budget"`) and is left unpaired anywhere else.
 */
function quotePartners(value: string): Map<number, number> {
  const partners = new Map<number, number>();
  const open = new Map<string, number[]>();
  let lastOpened = -2;
  for (let at = 0; at < value.length; at += 1) {
    const mark = value[at]!;
    const kind = QUOTE_KIND[mark];
    if (!kind) continue;
    const before = value[at - 1] ?? "";
    const after = value[at + 1] ?? "";
    if (APOSTROPHES.has(mark) && WORD_CHAR.test(before) && WORD_CHAR.test(after)) continue;
    const stack = open.get(kind) ?? [];
    open.set(kind, stack);
    const opens =
      OPENS_ONLY.has(mark) ||
      (!CLOSES_ONLY.has(mark) &&
        (OPEN_BEFORE.test(before) || lastOpened === at - 1 || (stack.length === 0 && WORD_CHAR.test(after))));
    if (opens) {
      stack.push(at);
      lastOpened = at;
      continue;
    }
    const start = stack.pop();
    if (start === undefined) continue;
    partners.set(start, at);
    partners.set(at, start);
  }
  return partners;
}

/**
 * Strip quotes around the whole title, and a stray one at either edge. A quote that closes
 * one inside the title stays: `Meeting with "Bob"` keeps its last mark.
 */
function stripEdgeQuotes(value: string): string {
  const last = value.length - 1;
  if (last < 0) return value;
  const isQuote = (at: number) => QUOTE_KIND[value[at]!] !== undefined;
  const partners = quotePartners(value);
  if (isQuote(0) && partners.get(0) === last) return value.slice(1, last);
  const start = isQuote(0) && !partners.has(0) ? 1 : 0;
  const end = last > 0 && isQuote(last) && !partners.has(last) ? last : value.length;
  return value.slice(start, end);
}

function stripTrailingPunct(value: string): string {
  let end = value.length;
  while (end > 0 && TITLE_TRAIL_PUNCT.has(value[end - 1]!)) end -= 1;
  return value.slice(0, end);
}

/** Strip wrapping quotes + trailing sentence punctuation until stable. */
function unwrapChatTitle(raw: string): string {
  let title = raw.trim();
  for (;;) {
    const prev = title;
    title = stripEdgeQuotes(title).trim();
    title = stripTrailingPunct(title).trim();
    title = stripEdgeQuotes(title).trim();
    if (title === prev) return title;
  }
}

/** Label for chat headers, drawer rows, and search results. */
export function displayChatTitle(
  title: string | null | undefined,
  options: ChatTitleDisplayOptions,
  t: (key: string) => string,
): string {
  const trimmed = title ? unwrapChatTitle(title) : "";
  if (trimmed) return trimmed;
  if (options.generating) return t("chat.title_generating");
  return t("common.untitled");
}

const PROVISIONAL_TITLE_MAX = 48;

function truncateTitle(title: string): string {
  if (title.length <= PROVISIONAL_TITLE_MAX) return title;
  return `${title.slice(0, PROVISIONAL_TITLE_MAX - 1).trimEnd()}…`;
}

/** The word an attachment-only first turn is titled with, in the app's language. */
const ATTACHMENT_TITLE_KEYS = { image: "chat.title_image", file: "chat.title_file" } as const;

type ProvisionalTitle = { line: string } | { attachment: keyof typeof ATTACHMENT_TITLE_KEYS };

function readProvisionalTitle(text: string | undefined): ProvisionalTitle | null {
  if (!text?.trim()) return null;
  const parsed = parseUserMessageContent(text);
  const caption = unwrapChatTitle(parsed.caption.split("\n")[0] ?? "");
  if (caption) return { line: truncateTitle(caption) };
  if (parsed.images.length > 0) return { attachment: "image" };
  if (parsed.files.length > 0 || parsed.hasFileAttachment) return { attachment: "file" };
  const line = unwrapChatTitle(text.trim().split("\n")[0] ?? "");
  return line ? { line: truncateTitle(line) } : null;
}

/** The title a first turn reads as, for tests: the drawer titles a line with the topic job,
 * so the app itself shows only the attachment word (`provisionalAttachmentTitle`). */
export function provisionalChatTitleForTest(text: string | undefined, t: (key: string) => string): string | null {
  const read = readProvisionalTitle(text);
  if (!read) return null;
  return "line" in read ? read.line : t(ATTACHMENT_TITLE_KEYS[read.attachment]);
}

/** Image/File only — never the user's first sentence (that is the topic job). */
export function provisionalAttachmentTitle(text: string | undefined, t: (key: string) => string): string | null {
  const read = readProvisionalTitle(text);
  return read && "attachment" in read ? t(ATTACHMENT_TITLE_KEYS[read.attachment]) : null;
}

const PLACEHOLDER_TITLES = new Set(["untitled", "new chat", "chat", "conversation", "new conversation"]);

/** Empty or boring labels still need the topic job. */
export function chatNeedsGeneratedTitle(title: string | null | undefined): boolean {
  const trimmed = unwrapChatTitle(title ?? "").toLowerCase();
  return !trimmed || PLACEHOLDER_TITLES.has(trimmed);
}

/** Trim quotes and enforce max length before PATCH /chats/{id}. */
export function sanitizeManualChatTitle(raw: string): string | null {
  const title = unwrapChatTitle(raw);
  if (!title || title.length > 80) return null;
  return title;
}
