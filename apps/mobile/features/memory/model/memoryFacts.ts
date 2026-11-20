import type { Memory } from "@/features/memory/types";

export const MEMORY_TEXT_MAX_LENGTH = 4000;

/** The server owns the freshness stamp; editing changes the remembered text. */
export function stripMemoryAsOf(text: string): string {
  return text.trim().replace(/^As of \d{4}-\d{2}-\d{2}:\s*/i, "").trim();
}

/**
 * Where a fact's "From" line goes: its chat, scrolled to the message that states it when
 * the server knows that message. None when the chat is gone (deleted chats clear the id).
 * The chat opens over the memory page; returnTo turns its header button into Back.
 */
export function memorySourceChatHref(
  fact: Pick<Memory, "source_chat_id" | "source_chat_title" | "source_message_id">,
): {
  pathname: "/";
  params: { chatId: string; returnTo: "memory"; highlightMessage?: string };
} | null {
  if (!fact.source_chat_id || !fact.source_chat_title) return null;
  return {
    pathname: "/",
    params: {
      chatId: fact.source_chat_id,
      returnTo: "memory",
      ...(fact.source_message_id ? { highlightMessage: fact.source_message_id } : {}),
    },
  };
}
