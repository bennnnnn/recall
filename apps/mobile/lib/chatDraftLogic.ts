export function resolveActiveChatId(
  chatId: string | null,
  draftChatId: string | null,
): string | null {
  return chatId ?? draftChatId;
}

export function shouldPreCreateDraft(options: {
  token: string | null;
  routeChatId: string | undefined;
  chatId: string | null;
  messagesLength: number;
  streaming: boolean;
}): boolean {
  return Boolean(
    options.token &&
      !options.routeChatId &&
      !options.chatId &&
      options.messagesLength === 0 &&
      !options.streaming,
  );
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
