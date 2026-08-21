export type ChatTitleDisplayOptions = {
  /** True while waiting for auto-generated title after first exchange. */
  generating?: boolean;
};

const TITLE_QUOTES = new Set([`"`, `'`, `\u201c`, `\u201d`, `\u2018`, `\u2019`]);
const TITLE_TRAIL_PUNCT = new Set([".", "!", "?", ",", ";", ":"]);

function stripEdgeQuotes(value: string): string {
  let start = 0;
  let end = value.length;
  while (start < end && TITLE_QUOTES.has(value[start]!)) start += 1;
  while (end > start && TITLE_QUOTES.has(value[end - 1]!)) end -= 1;
  return value.slice(start, end);
}

function stripTrailingPunct(value: string): string {
  let end = value.length;
  while (end > 0 && TITLE_TRAIL_PUNCT.has(value[end - 1]!)) end -= 1;
  return value.slice(0, end);
}

/** Strip wrapping quotes + trailing sentence punctuation until stable. */
export function unwrapChatTitle(raw: string): string {
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

/** Trim quotes and enforce max length before PATCH /chats/{id}. */
export function sanitizeManualChatTitle(raw: string): string | null {
  const title = unwrapChatTitle(raw);
  if (!title || title.length > 80) return null;
  return title;
}
