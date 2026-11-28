/**
 * A chat the server no longer has (deleted on another device, or a draft chat its retention let
 * go) goes as this phone's own delete takes it: its drawer row, saved thread and files
 * (`chatsDeleted`), its unsent messages to New chat's composer (`useUnsentOfDeletedChats`), and
 * the open chat, which gives way to New chat. The person is told once per chat, in words that
 * name no device (`subscribeChatGone`, drawn by `ChatGoneNotice`). Every read and change of a
 * chat that finds it gone comes here.
 */
import { abandonActiveChatIfDeleted } from "@/features/chat/drawer/drawer";
import { isGone } from "@/lib/api/gone";
import { emitAppEvent } from "@/lib/appEvents";
import { createListenerSet } from "@/lib/listenerSet";

/** The chats the person was told are gone: server ids, which no other account has. */
const toldChatIds = new Set<string>();
const goneListeners = createListenerSet<[chatId: string]>();

/** Told once per chat: the notice of a chat found gone. */
export function subscribeChatGone(listener: (chatId: string) => void): () => void {
  return goneListeners.subscribe(listener);
}

/** The chat is gone on the server: take it away here and say so once. */
export function forgetGoneChat(chatId: string): void {
  const first = !toldChatIds.has(chatId);
  toldChatIds.add(chatId);
  emitAppEvent("chatsDeleted", { chatIds: [chatId] });
  abandonActiveChatIfDeleted([chatId]);
  if (first) goneListeners.emit(chatId);
}

/** `forgetGoneChat` when `error` says the chat is gone; true when it did. */
export function forgetChatIfGone(chatId: string, error: unknown): boolean {
  if (!isGone(error)) return false;
  forgetGoneChat(chatId);
  return true;
}
