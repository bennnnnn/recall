import { api, type Chat, type ChatList } from "@/lib/api";
import { getSessionGeneration, requireTokenSession } from "@/lib/auth";
import { clearKnownAssistantChats } from "@/lib/chatDraftLogic";
import { allChatsFromGroups, emptyChatList } from "@/lib/chat/chatListSections";
import { CHAT_LIST_STALE_MS } from "@/lib/drawerChatList";

type ListUpdate = (groups: ChatList) => ChatList;
type CacheState = {
  session: number;
  data?: ChatList;
  fetchedAt?: number;
  pending?: { task: Promise<ChatList | null>; updates: ListUpdate[] };
  createdChat?: Chat;
  skipCreatedSuggestions: boolean;
};
function newCache(): CacheState {
  return { session: getSessionGeneration(), skipCreatedSuggestions: false };
}
let cache: CacheState = { session: -1, skipCreatedSuggestions: false };
function currentCache(): CacheState {
  if (cache.session !== getSessionGeneration()) cache = newCache();
  return cache;
}

/** POST /chats body — first reply inserts the drawer row without GET /chats/{id}. */
export function rememberCreatedChat(chat: Chat): void {
  const state = currentCache();
  state.createdChat = chat;
  state.skipCreatedSuggestions = true;
}

export function peekCreatedChat(id: string): Chat | undefined {
  const chat = currentCache().createdChat;
  return chat?.id === id ? chat : undefined;
}

/** True once after Home create, so the first stream-end does not GET /suggestions. */
export function consumeCreatedSuggestionSkip(id: string): boolean {
  const state = currentCache();
  if (state.createdChat?.id !== id || !state.skipCreatedSuggestions) return false;
  state.skipCreatedSuggestions = false;
  return true;
}

export function getCachedChatList(): ChatList | undefined {
  return currentCache().data;
}

/** Drawer row already has title / pin / class id — skip GET /chats/{id}. */
export function getCachedChat(id: string): Chat | undefined {
  const list = getCachedChatList();
  return list ? allChatsFromGroups(list).find((chat) => chat.id === id) : undefined;
}

export function getChatListFetchedAt(): number | undefined {
  return currentCache().fetchedAt;
}

export function isChatListFresh(): boolean {
  const state = currentCache();
  return state.data != null && state.fetchedAt != null && Date.now() - state.fetchedAt < CHAT_LIST_STALE_MS;
}

export function setChatListCache(data: ChatList): void {
  const state = currentCache();
  state.data = data;
  state.fetchedAt = Date.now();
  state.pending?.updates.push(() => data);
}

/** Replay edits over an already-running read so it cannot restore a deleted/old row. */
export function updateChatListCache(update: ListUpdate): ChatList {
  const state = currentCache();
  state.data = update(state.data ?? emptyChatList());
  state.pending?.updates.push(update);
  return state.data;
}

export function invalidateChatListCache(): void {
  // Replacing ownership fences reads already in flight, including prefetches.
  cache = newCache();
  clearKnownAssistantChats();
}

export async function fetchChatList(
  token: string,
  opts?: { force?: boolean },
): Promise<ChatList | null> {
  try { requireTokenSession(token); } catch { return null; }
  const state = currentCache();
  if (!opts?.force && isChatListFresh()) return state.data!;
  if (state.pending) return state.pending.task;
  const updates: ListUpdate[] = [];
  const task = (async () => {
    try {
      const data = await api.listChats(token);
      if (currentCache() !== state) return null;
      state.data = updates.reduce((groups, update) => update(groups), {
        ...data, archived: data.archived ?? [],
      });
      state.fetchedAt = Date.now();
      return state.data;
    } catch {
      return null;
    }
  })();
  const pending = { task, updates };
  state.pending = pending;
  try { return await task; }
  finally { if (state.pending === pending) state.pending = undefined; }
}

/** Warm GET /chats so the drawer can paint titles without a spinner. */
export function prefetchChatList(token: string): void {
  void fetchChatList(token);
}
