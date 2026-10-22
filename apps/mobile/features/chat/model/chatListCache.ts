import { api, type Chat, type ChatList } from "@/lib/api";
import { clearKnownAssistantChats } from "@/features/chat/model/draftLogic";
import { allChatsFromGroups, emptyChatList } from "@/features/chat/model/listSections";
import {
  SessionResourceCache,
  type FailureReporter,
  type ResourceResult,
  type ResourceUpdate,
} from "@/lib/cache/sessionResource";
import { CHAT_LIST_STALE_MS } from "@/features/chat/drawer/drawerChatList";

const LIST = "chats";
const resource = new SessionResourceCache<typeof LIST, ChatList, { createdChat?: Chat }>({
  staleMs: CHAT_LIST_STALE_MS,
  // The first chat is inserted before the first full read and must not count as one.
  empty: emptyChatList,
  sessionState: () => ({}),
});

/** POST /chats body — first reply inserts the drawer row without GET /chats/{id}. */
export function rememberCreatedChat(chat: Chat): void {
  resource.state().createdChat = chat;
}

export function peekCreatedChat(id: string): Chat | undefined {
  const chat = resource.state().createdChat;
  return chat?.id === id ? chat : undefined;
}

export function getCachedChatList(): ChatList | undefined {
  return resource.get(LIST);
}

/** Drawer row already has title / pin / class id — skip GET /chats/{id}. */
export function getCachedChat(id: string): Chat | undefined {
  const list = getCachedChatList();
  return list ? allChatsFromGroups(list).find((chat) => chat.id === id) : undefined;
}

export function getChatListFetchedAt(): number | undefined {
  return resource.fetchedAt(LIST);
}

export function isChatListFresh(): boolean {
  return resource.isFresh(LIST);
}

export function setChatListCache(data: ChatList): void {
  resource.set(LIST, data);
}

/** Replay edits over an already-running read so it cannot restore a deleted/old row. */
export function updateChatListCache(update: ResourceUpdate<ChatList>): ChatList {
  return resource.update(LIST, update) ?? emptyChatList();
}

export function invalidateChatListCache(): void {
  resource.invalidate();
  clearKnownAssistantChats();
}

export function fetchChatList(
  token: string,
  opts?: { force?: boolean; report?: FailureReporter },
): Promise<ResourceResult<ChatList>> {
  return resource.fetch(LIST, token, async () => {
    const data = await api.listChats(token);
    return { ...data, archived: data.archived ?? [] };
  }, opts);
}
