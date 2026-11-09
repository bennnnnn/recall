import type { Chat, ChatList } from "@/lib/api";
import { activeChatsFromGroups, emptyChatList, insertChatByRecency } from "@/features/chat/model/listSections";
import { CONTEXT_REFRESH_STALE_MS } from "@/lib/cache/contextRefresh";

/** How long a GET /chats response stays fresh for drawer paint / prefetch. */
export const CHAT_LIST_STALE_MS = CONTEXT_REFRESH_STALE_MS;

/** "full" shows the spinner; "revalidate" reads behind the rows shown, and not while they are fresh. */
type DrawerChatFetchMode = "skip" | "full" | "revalidate";

/**
 * Opening the sidebar paints from cache after the first load, and reads the list again
 * behind it once that read is older than `CHAT_LIST_STALE_MS`: a chat started on another
 * device never showed until a pull-to-refresh or a relaunch. Closed-drawer idle warm
 * lives in useDrawerChatList.
 */
export function drawerChatFetchMode(opts: {
  isDrawerOpen: boolean;
  hasToken: boolean;
  hasLoadedOnce: boolean;
}): DrawerChatFetchMode {
  if (!opts.isDrawerOpen || !opts.hasToken) return "skip";
  if (opts.hasLoadedOnce) return "revalidate";
  return "full";
}

/** Closed-drawer idle warm is for first paint, not for closing the sidebar. */
export function shouldWarmClosedDrawerChatList(opts: {
  hasToken: boolean;
  isDrawerOpen: boolean;
  hasLoadedOnce: boolean;
}): boolean {
  return opts.hasToken && !opts.isDrawerOpen && !opts.hasLoadedOnce;
}

/** Insert a chat into drawer groups if it is not already listed. */
export function insertChatIntoGroups(groups: ChatList, chat: Chat): ChatList {
  const listed = activeChatsFromGroups(groups).concat(groups.archived);
  if (listed.some((row) => row.id === chat.id)) {
    return groups;
  }

  return insertChatByRecency(groups, chat);
}

export { emptyChatList };
