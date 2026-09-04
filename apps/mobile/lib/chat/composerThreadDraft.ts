/** Composer slot for New Chat (no `chatId` in the route). */
export const COMPOSER_NEW_THREAD_KEY = "new";

export function composerThreadKey(
  routeChatId: string | null | undefined,
): string {
  return typeof routeChatId === "string" && routeChatId.length > 0
    ? routeChatId
    : COMPOSER_NEW_THREAD_KEY;
}

/** Save the leaving thread's text and return the draft for `toKey`. Mutates `drafts`. */
export function takeThreadDraft(
  drafts: Map<string, string>,
  fromKey: string,
  toKey: string,
  currentText: string,
): string {
  if (fromKey === toKey) return currentText;
  drafts.set(fromKey, currentText);
  return drafts.get(toKey) ?? "";
}

/**
 * New Chat just received a real id. Keep the visible composer (usually empty
 * after send, or a follow-up typed while create was in flight). If the user
 * already opened another thread, leave that composer alone.
 */
export function adoptNewComposerThread(
  drafts: Map<string, string>,
  fromKey: string,
  toKey: string,
  currentText: string,
): string {
  if (fromKey === toKey) return toKey;
  if (fromKey !== COMPOSER_NEW_THREAD_KEY) return fromKey;
  drafts.set(COMPOSER_NEW_THREAD_KEY, "");
  drafts.set(toKey, currentText);
  return toKey;
}
