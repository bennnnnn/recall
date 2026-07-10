import type { Chat, ChatList } from "@/lib/api";
import { activeChatsFromGroups } from "@/lib/chatListSections";

export function toggleChatSelection(selected: ReadonlySet<string>, chatId: string): Set<string> {
  const next = new Set(selected);
  if (next.has(chatId)) next.delete(chatId);
  else next.add(chatId);
  return next;
}

export function selectAllChatIds(chats: readonly Chat[]): Set<string> {
  return new Set(chats.map((chat) => chat.id));
}

export function clearChatSelection(): Set<string> {
  return new Set();
}

export function chatsFromSelection(groups: ChatList, selectedIds: ReadonlySet<string>): Chat[] {
  if (selectedIds.size === 0) return [];
  const listed = activeChatsFromGroups(groups).concat(groups.archived);
  return listed.filter((chat) => selectedIds.has(chat.id));
}

export function archiveBulkTargets(chats: readonly Chat[]): Chat[] {
  return chats.filter((chat) => !chat.archived);
}
