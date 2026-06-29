export type ChatTitleDisplayOptions = {
  /** True while waiting for auto-generated title after first exchange. */
  generating?: boolean;
};

/** Label for chat headers, drawer rows, and search results. */
export function displayChatTitle(
  title: string | null | undefined,
  options: ChatTitleDisplayOptions,
  t: (key: string) => string,
): string {
  const trimmed = title?.trim();
  if (trimmed) return trimmed;
  if (options.generating) return t("chat.title_generating");
  return t("common.untitled");
}

/** Trim quotes and enforce max length before PATCH /chats/{id}. */
export function sanitizeManualChatTitle(raw: string): string | null {
  const title = raw.trim().replace(/^["']|["']$/g, "").trim();
  if (!title || title.length > 80) return null;
  return title;
}
