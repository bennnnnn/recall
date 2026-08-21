import { api, type ChatList } from "@/lib/api";
import { StaleResourceCache } from "@/lib/cache/staleResource";
import { CHAT_LIST_STALE_MS } from "@/lib/drawerChatList";

const CHAT_LIST_KEY = "chat-list";
const resource = new StaleResourceCache<string, ChatList>(CHAT_LIST_STALE_MS);

export function getCachedChatList(): ChatList | undefined {
  return resource.get(CHAT_LIST_KEY);
}

export function getChatListFetchedAt(): number | undefined {
  return resource.getFetchedAt(CHAT_LIST_KEY);
}

export function isChatListFresh(): boolean {
  return resource.isFresh(CHAT_LIST_KEY);
}

export function setChatListCache(data: ChatList): void {
  resource.set(CHAT_LIST_KEY, data);
}

export function invalidateChatListCache(): void {
  resource.invalidate(CHAT_LIST_KEY);
}

export async function fetchChatList(
  token: string,
  opts?: { force?: boolean },
): Promise<ChatList | null> {
  try {
    return await resource.fetch(
      CHAT_LIST_KEY,
      async () => {
      const data = await api.listChats(token);
      const normalized: ChatList = {
        pinned: data.pinned,
        today: data.today,
        yesterday: data.yesterday,
        last_7_days: data.last_7_days,
        this_month: data.this_month,
        older: data.older,
        archived: data.archived ?? [],
      };
      return normalized;
      },
      opts,
    );
  } catch {
    return null;
  }
}

/** Warm GET /chats so the drawer can paint titles without a spinner. */
export function prefetchChatList(token: string): void {
  resource.prefetch(CHAT_LIST_KEY, async () => {
    const data = await api.listChats(token);
    return { ...data, archived: data.archived ?? [] };
  });
}
