import type { Chat, ChatList } from "@/lib/api";
import { activeChatsFromGroups, emptyChatList } from "@/lib/chatListSections";

/** How long a GET /chats response stays fresh for drawer paint / prefetch. */
export const CHAT_LIST_STALE_MS = 20_000;

export type DrawerChatFetchMode = "skip" | "full" | "background";

/**
 * When the open drawer should run a spinner (`full`) or silent refresh
 * (`background`) listChats. Closed-drawer idle warm lives in
 * useDrawerChatList (via chatListCache) — this helper stays spinner-gated so
 * ConversationList mounting under DrawerShell never flips `loading` while
 * closed.
 */
export function drawerChatFetchMode(opts: {
  isDrawerOpen: boolean;
  hasToken: boolean;
  hasLoadedOnce: boolean;
  lastFetchedAt: number;
  chatCount: number;
  now: number;
  staleMs: number;
}): DrawerChatFetchMode {
  if (!opts.isDrawerOpen || !opts.hasToken) return "skip";
  if (!opts.hasLoadedOnce || opts.lastFetchedAt === 0) return "full";
  const stale =
    opts.now - opts.lastFetchedAt > opts.staleMs || opts.chatCount === 0;
  return stale ? "background" : "skip";
}

/** Insert a chat into drawer groups if it is not already listed. */
export function insertChatIntoGroups(groups: ChatList, chat: Chat): ChatList {
  const listed = activeChatsFromGroups(groups).concat(groups.archived);
  if (listed.some((row) => row.id === chat.id)) {
    return groups;
  }

  if (chat.archived) {
    return { ...groups, archived: [chat, ...groups.archived] };
  }
  if (chat.pinned) {
    return { ...groups, pinned: [chat, ...groups.pinned] };
  }
  return { ...groups, today: [chat, ...groups.today] };
}

export { emptyChatList };
