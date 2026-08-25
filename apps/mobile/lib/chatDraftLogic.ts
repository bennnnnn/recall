const emptyChatChecks = new Map<string, Promise<void>>();

/** One empty-check per chat — New chat + route-clear used to list twice. */
export function shareEmptyChatCheck(
  chatId: string,
  run: () => Promise<void>,
): Promise<void> {
  const existing = emptyChatChecks.get(chatId);
  if (existing) return existing;
  const task = run().finally(() => {
    if (emptyChatChecks.get(chatId) === task) emptyChatChecks.delete(chatId);
  });
  emptyChatChecks.set(chatId, task);
  return task;
}

/** Route-change effect already discards the previous routed chat. */
export function shouldDiscardOnNewChat(routeChatId: string | undefined): boolean {
  return routeChatId == null;
}

export function resolveActiveChatId(
  chatId: string | null,
  draftChatId: string | null,
): string | null {
  return chatId ?? draftChatId;
}

/** Skip the empty-check GET when the thread already has an assistant reply. */
export function shouldProbeEmptyChat(hasAssistant: boolean): boolean {
  return !hasAssistant;
}

export function shouldWarmDraftSocket(options: {
  token: string | null;
  draftChatId: string | null;
  chatId: string | null;
  streaming: boolean;
}): boolean {
  return Boolean(
    options.token &&
      options.draftChatId &&
      !options.chatId &&
      !options.streaming,
  );
}
