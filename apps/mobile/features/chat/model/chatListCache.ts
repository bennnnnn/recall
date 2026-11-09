import { api, type Chat, type ChatList } from "@/lib/api";
import { getSessionGeneration, requireTokenSession } from "@/lib/auth";
import { abandonActiveChatIfDeleted } from "@/features/chat/drawer/drawer";
import { clearKnownAssistantChats } from "@/features/chat/model/draftLogic";
import {
  allChatsFromGroups,
  appendArchivedChats,
  appendOlderChats,
  emptyChatList,
  keepLoadedPages,
  regroupChatsByRecency,
} from "@/features/chat/model/listSections";
import {
  SessionResourceCache,
  type FailureReporter,
  type ResourceResult,
  type ResourceUpdate,
} from "@/lib/cache/sessionResource";
import { CHAT_LIST_STALE_MS } from "@/features/chat/drawer/drawerChatList";
import { emitAppEvent, onAppEvent } from "@/lib/appEvents";
import { scheduleIdleTask } from "@/lib/scheduleIdle";
import { tokenSubject } from "@/lib/tokenSubject";

type ListSession = {
  createdChat?: Chat;
  /** The signed-in account; the file is written for it. */
  owner?: string;
  /** The list the file holds now: read back from it, or last written to it. */
  stored?: ChatList;
  restore?: Promise<boolean>;
  saveQueued?: boolean;
  /**
   * Set when a change to many chats dropped the list (`invalidateChatListCache`): "rows-removed"
   * when that change took away rows a screen shows (Delete all, Archive all).
   */
  dropped?: "rows-kept" | "rows-removed";
  /** Chats this phone changed (`noteChatListChanged`), and how many of those the last read saw. */
  changes?: number;
  changesRead?: number;
};

const LIST = "chats";
const resource = new SessionResourceCache<typeof LIST, ChatList, ListSession>({
  staleMs: CHAT_LIST_STALE_MS,
  // The first chat is inserted before the first full read and must not count as one. A
  // dropped list is unknown: an edit then waits for the read, never makes a list of its own.
  empty: (): ChatList | undefined => (resource.state().dropped ? undefined : emptyChatList()),
  sessionState: () => ({}),
});
resource.subscribe(saveSoon);
// A picture saved into a chat moved that chat up the list.
onAppEvent("attachmentAdded", () => noteChatListChanged());

/** The file layer loads expo-file-system: only a restore or a write needs it. */
const listFile = () => import("@/features/chat/model/chatListFile");

/** The account a token of this session belongs to; null for a token another session holds. */
function ownerOf(token: string): string | null {
  try {
    requireTokenSession(token);
  } catch {
    return null;
  }
  const owner = tokenSubject(token);
  if (owner) resource.state().owner ??= owner;
  return owner;
}

/**
 * Write the list to disk once the phone is idle, for a cold start to paint: a
 * list this session read, or restored and then edited. A list that only holds
 * edits made before any read is not the account's list and is never written.
 */
function saveSoon(): void {
  const state = resource.state();
  if (state.saveQueued) return;
  state.saveQueued = true;
  const current = resource.lease();
  scheduleIdleTask(() => {
    state.saveQueued = false;
    const list = resource.get(LIST);
    if (!current() || !state.owner || !list || list === state.stored) return;
    if (resource.fetchedAt(LIST) === undefined && state.stored === undefined) return;
    state.stored = list;
    const owner = state.owner;
    void listFile().then((file) => file.writeStoredChatList(owner, list)).catch(() => {});
  });
}

/**
 * Show the chats this account had last time while the drawer reads them again:
 * a cold start paints the drawer at once. The restored list is never fresh, so
 * that read still happens, and it never replaces one already read or edited.
 */
export function restoreChatList(token: string): Promise<boolean> {
  const owner = ownerOf(token);
  if (!owner) return Promise.resolve(false);
  const state = resource.state();
  state.restore ??= (async () => {
    const session = getSessionGeneration();
    const current = resource.lease();
    const list = await listFile().then((file) => file.readStoredChatList(owner)).catch(() => null);
    if (!list || !current() || !resource.seed(LIST, list, session)) return false;
    state.stored = list;
    return true;
  })();
  return state.restore;
}

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

/** Called on every change to the cached list (read with `getCachedChatList`). */
export function subscribeChatList(listener: () => void): () => void {
  return resource.subscribe(listener);
}

/**
 * The cached list with each dated chat under the heading it has now, in the phone's
 * zone (`regroupChatsByRecency`): a list restored from disk or held across midnight.
 * An edit, so a read running now and the disk copy keep it too.
 */
export function regroupCachedChatList(): ChatList | undefined {
  const list = resource.get(LIST);
  if (!list || regroupChatsByRecency(list) === list) return list;
  return resource.update(LIST, (current) => regroupChatsByRecency(current));
}

/** Drawer row already has title / pin / class id — skip GET /chats/{id}. */
export function getCachedChat(id: string): Chat | undefined {
  const list = getCachedChatList();
  return list ? allChatsFromGroups(list).find((chat) => chat.id === id) : undefined;
}

/**
 * The drawer row as the server sent it this session. A list restored from disk
 * paints the drawer, but its titles may predate a rename on another device.
 */
export function getFetchedChat(id: string): Chat | undefined {
  return getChatListFetchedAt() != null ? getCachedChat(id) : undefined;
}

export function getChatListFetchedAt(): number | undefined {
  return resource.fetchedAt(LIST);
}

export function isChatListFresh(): boolean {
  return resource.isFresh(LIST);
}

/** Tests only: a completed read of `data`, already in the cache. The app fills it with `fetchChatList`. */
export function seedChatListCacheForTest(data: ChatList): void {
  resource.set(LIST, data);
}

/**
 * Replay edits over an already-running read so it cannot restore a deleted/old row. After a
 * drop it returns nothing until the list is read again: the edit only rides on a read running.
 * Built on an empty list, the drawer showed only the chats touched since an unarchive, and
 * built on the rows shown, Delete all brought its chats back (iOS Simulator, 2026-11-07).
 */
export function updateChatListCache(update: ResourceUpdate<ChatList>): ChatList | undefined {
  return resource.update(LIST, update);
}

/**
 * Sign-out, or a change to many chats at once: forget the list, on disk too. The drawer reads
 * it again (in the background, so Home's last chat comes back), keeping the rows it shows
 * meanwhile (an unarchive left every one in place), unless `rowsRemoved` says the change
 * took them away (Delete all, Archive all): then it drops them too, so none comes back.
 */
export function invalidateChatListCache({ rowsRemoved = false } = {}): Promise<void> {
  resource.invalidate({ dropped: rowsRemoved ? "rows-removed" : "rows-kept" });
  clearKnownAssistantChats();
  return listFile().then((file) => file.clearStoredChatList()).catch(() => {});
}

/**
 * A chat deleted outside the chat screens (Settings' archived chats) goes as the drawer's own
 * delete takes it: its row, saved thread and files (`chatsDeleted`), the open chat if it is
 * that one, and the list read again with every other row kept.
 */
export function forgetDeletedChat(chatId: string): Promise<void> {
  emitAppEvent("chatsDeleted", { chatIds: [chatId] });
  abandonActiveChatIfDeleted([chatId]);
  return invalidateChatListCache();
}

/**
 * This phone changed a chat the list shows: a turn it finished (the chat moves up), a title it
 * received, a pin, an archive, a delete. The drawer reads the list again on its next open; until
 * then, and with nothing changed, it shows the list it holds (2026-11-08: a GET /chats on every
 * open, ten in one run, nearly all 304).
 */
export function noteChatListChanged(): void {
  const state = resource.state();
  state.changes = (state.changes ?? 0) + 1;
}

/** A chat changed since the last read of the list began (`noteChatListChanged`). */
export function chatListChangedSinceRead(): boolean {
  const state = resource.state();
  return (state.changes ?? 0) !== (state.changesRead ?? 0);
}

/** The list was dropped (`invalidateChatListCache`) and is not read since. */
export function isChatListDropped(): boolean {
  return resource.get(LIST) === undefined && resource.state().dropped !== undefined;
}

/** The rows a screen shows were removed with the list (Delete all), and it is not read since. */
export function chatListRowsRemoved(): boolean {
  return isChatListDropped() && resource.state().dropped === "rows-removed";
}

export async function fetchChatList(
  token: string,
  opts?: { force?: boolean; report?: FailureReporter },
): Promise<ResourceResult<ChatList>> {
  const result = await resource.fetch(LIST, token, async () => {
    const state = resource.state();
    // A change made while this read runs may not be in it: it stays to read.
    const changes = state.changes ?? 0;
    const data = await api.listChats(token);
    state.changesRead = changes;
    const fresh = { ...data, archived: data.archived ?? [] };
    // GET /chats is the first page: the pages this session read below it stay (a restored list's do not).
    const shown = resource.fetchedAt(LIST) === undefined ? undefined : resource.get(LIST);
    return shown ? keepLoadedPages(shown, fresh) : fresh;
  }, opts);
  if (!result.error) ownerOf(token);
  return result;
}

/**
 * Read the next page of older dated chats into the cached list; null when there is none.
 * A refresh that landed meanwhile changed the cursor, and the page is dropped.
 */
export async function fetchOlderChats(token: string): Promise<ChatList | null> {
  const cursor = getCachedChatList()?.next_cursor;
  if (!cursor) return null;
  const session = getSessionGeneration();
  const older = await api.listOlderChats(token, cursor);
  // Another account signed in meanwhile: the page is not theirs.
  return resource.update(LIST, (current) =>
    current.next_cursor === cursor ? appendOlderChats(current, older) : current, session) ?? null;
}

/**
 * Read the next page of archived chats into the cached list; null when there is none.
 * Past the drawer's first page they were out of reach (only the newest 50 were listed).
 */
export async function fetchMoreArchivedChats(token: string): Promise<ChatList | null> {
  const cursor = getCachedChatList()?.archived_next_cursor;
  if (!cursor) return null;
  const session = getSessionGeneration();
  const page = await api.listArchivedChats(token, cursor);
  return resource.update(LIST, (current) =>
    current.archived_next_cursor === cursor ? appendArchivedChats(current, page) : current, session) ?? null;
}
