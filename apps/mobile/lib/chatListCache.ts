import { api, type ChatList } from "@/lib/api";
import { CHAT_LIST_STALE_MS } from "@/lib/drawerChatList";

type CacheEntry = {
  data: ChatList;
  fetchedAt: number;
};

let cache: CacheEntry | null = null;
let inflight: Promise<ChatList | null> | null = null;

export function getCachedChatList(): ChatList | undefined {
  return cache?.data;
}

export function getChatListFetchedAt(): number | undefined {
  return cache?.fetchedAt;
}

export function isChatListFresh(): boolean {
  if (!cache) return false;
  return Date.now() - cache.fetchedAt < CHAT_LIST_STALE_MS;
}

export function setChatListCache(data: ChatList): void {
  cache = { data, fetchedAt: Date.now() };
}

export function invalidateChatListCache(): void {
  cache = null;
  inflight = null;
}

export async function fetchChatList(
  token: string,
  opts?: { force?: boolean },
): Promise<ChatList | null> {
  if (!opts?.force && isChatListFresh()) {
    return cache!.data;
  }

  if (inflight) return inflight;

  const task = (async () => {
    try {
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
      setChatListCache(normalized);
      return normalized;
    } catch {
      return null;
    } finally {
      inflight = null;
    }
  })();

  inflight = task;
  return task;
}

/** Warm GET /chats so the drawer can paint titles without a spinner. */
export function prefetchChatList(token: string): void {
  if (isChatListFresh() || inflight) return;
  void fetchChatList(token);
}
