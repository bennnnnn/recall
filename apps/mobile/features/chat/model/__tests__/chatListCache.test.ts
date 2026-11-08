import { api } from "@/lib/api";
import {
  chatListRowsRemoved,
  fetchChatList,
  forgetDeletedChat,
  isChatListDropped,
  fetchMoreArchivedChats,
  fetchOlderChats,
  getCachedChat,
  getCachedChatList,
  getFetchedChat,
  peekCreatedChat,
  rememberCreatedChat,
  getChatListFetchedAt,
  invalidateChatListCache,
  isChatListFresh,
  restoreChatList,
  seedChatListCacheForTest,
  updateChatListCache,
} from "@/features/chat/model/chatListCache";
import { clearStoredChatList, writeStoredChatList } from "@/features/chat/model/chatListFile";
import { registerNewChat, setActiveChatIdGlobal } from "@/features/chat/drawer/drawer";
import { onAppEvent } from "@/lib/appEvents";
import {
  markChatHasAssistant,
  shouldProbePreviousChat,
} from "@/features/chat/model/draftLogic";
import type { ChatList } from "@/lib/api";

jest.mock("@/lib/api", () => ({
  api: {
    listChats: jest.fn(),
    listOlderChats: jest.fn(),
    listArchivedChats: jest.fn(),
  },
}));

const mockStored = new Map<string, ChatList>();
jest.mock("@/features/chat/model/chatListFile", () => ({
  readStoredChatList: jest.fn(async (userId: string) => mockStored.get(userId) ?? null),
  writeStoredChatList: jest.fn(async (userId: string, list: ChatList) => { mockStored.set(userId, list); }),
  clearStoredChatList: jest.fn(async () => { mockStored.clear(); }),
}));
const mockIdle: (() => void)[] = [];
jest.mock("@/lib/scheduleIdle", () => ({
  scheduleIdleTask: (task: () => void) => { mockIdle.push(task); return () => {}; },
}));

let mockSession = 0;
jest.mock("@/lib/auth", () => ({
  getSessionGeneration: () => mockSession,
  requireTokenSession: jest.fn(),
  SessionChangedError: class SessionChangedError extends Error {},
}));
const listChats = api.listChats as jest.Mock;

const sample: ChatList = {
  pinned: [],
  today: [
    {
      id: "c1",
      title: "Hello",
      model: "free-chat",
      pinned: false,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    },
  ],
  yesterday: [],
  last_7_days: [],
  this_month: [],
  older: [],
  archived: [],
};

describe("chatListCache", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockSession = 0;
    invalidateChatListCache();
  });

  it("returns cached list without refetching when fresh", async () => {
    seedChatListCacheForTest(sample);
    expect(isChatListFresh()).toBe(true);
    expect(getCachedChatList()).toEqual(sample);
    expect(getChatListFetchedAt()).toEqual(expect.any(Number));

    const result = await fetchChatList("token");
    expect(result).toEqual({ data: sample, error: null });
    expect(listChats).not.toHaveBeenCalled();
  });

  it("dedupes concurrent fetches", async () => {
    let resolveFetch!: (value: ChatList) => void;
    listChats.mockReturnValue(
      new Promise((resolve) => {
        resolveFetch = resolve;
      }),
    );

    const first = fetchChatList("token", { force: true });
    const second = fetchChatList("token", { force: true });
    resolveFetch(sample);

    const [a, b] = await Promise.all([first, second]);
    expect(a).toEqual({ data: sample, error: null });
    expect(b).toEqual({ data: sample, error: null });
    expect(listChats).toHaveBeenCalledTimes(1);
  });

  it("remembers the POST /chats body until logout invalidates", () => {
    rememberCreatedChat(sample.today[0]);
    expect(peekCreatedChat("c1")?.title).toBe("Hello");
    expect(peekCreatedChat("other")).toBeUndefined();
    invalidateChatListCache();
    expect(peekCreatedChat("c1")).toBeUndefined();
  });

  it("clears known-assistant chats on logout invalidate", () => {
    markChatHasAssistant("c1");
    expect(
      shouldProbePreviousChat({ chatId: "c1", messagesHadAssistant: false }),
    ).toBe(false);
    invalidateChatListCache();
    expect(
      shouldProbePreviousChat({ chatId: "c1", messagesHadAssistant: false }),
    ).toBe(true);
  });

  it("finds a drawer row without another GET /chats/{id}", () => {
    seedChatListCacheForTest({
      ...sample,
      archived: [
        {
          id: "old",
          title: "Archived",
          model: "free-chat",
          pinned: false,
          archived: true,
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
        },
      ],
    });
    expect(getCachedChat("c1")?.title).toBe("Hello");
    expect(getCachedChat("old")?.archived).toBe(true);
    expect(getCachedChat("missing")).toBeUndefined();
  });

  it("normalizes missing archived to an empty array", async () => {
    const { archived: _omit, ...withoutArchived } = sample;
    listChats.mockResolvedValue(withoutArchived);
    const result = await fetchChatList("token", { force: true });
    expect(result.data?.archived).toEqual([]);
  });
});


it("cannot refill an invalidated cache from an older read", async () => {
  invalidateChatListCache();
  let finish!: (value: ChatList) => void;
  listChats.mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
  const old = fetchChatList("token");
  invalidateChatListCache();
  const newList = { ...sample, today: [{ ...sample.today[0], id: "new-account" }] };
  listChats.mockResolvedValueOnce(newList);
  await fetchChatList("new-token");
  finish(sample);
  expect(await old).toEqual({ data: null, error: expect.any(Error) });
  expect(getCachedChatList()).toEqual(newList);
});

it("isolates cached rows, created chat and inflight requests by account session", async () => {
  invalidateChatListCache();
  seedChatListCacheForTest(sample);
  rememberCreatedChat(sample.today[0]);
  let finish!: (value: ChatList) => void;
  listChats.mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
  const old = fetchChatList("token", { force: true });
  mockSession++;
  expect(getCachedChatList()).toBeUndefined();
  expect(peekCreatedChat("c1")).toBeUndefined();
  finish(sample);
  expect(await old).toEqual({ data: null, error: expect.any(Error) });
  expect(getCachedChatList()).toBeUndefined();
});

it("replays local edits on a late list response while retaining other server rows", async () => {
  invalidateChatListCache();
  seedChatListCacheForTest(sample);
  let finish!: (value: ChatList) => void;
  listChats.mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
  const read = fetchChatList("token", { force: true });
  updateChatListCache((groups) => ({ ...groups, today: groups.today.filter((chat) => chat.id !== "c1") }));
  const incoming = { ...sample, today: [...sample.today, { ...sample.today[0], id: "server-new" }] };
  finish(incoming);
  expect((await read).data?.today.map((chat) => chat.id)).toEqual(["server-new"]);
  expect(getCachedChat("c1")).toBeUndefined();
});

it("keeps optimistic first-chat insertion from suppressing the first full list read", async () => {
  // A new session, never read: the first chat is listed before the list is.
  mockSession++;
  expect(updateChatListCache((groups) => ({ ...groups, today: sample.today }))?.today).toEqual(sample.today);
  expect(isChatListFresh()).toBe(false);
  listChats.mockResolvedValueOnce(sample);
  await fetchChatList("token");
  expect(isChatListFresh()).toBe(true);
});


it("makes no list from an edit after a drop, and replays one made during the next read over it", async () => {
  // Built on an empty list, an unarchive left only the chats touched since; built on the rows
  // shown, Delete all brought its chats back (iOS Simulator, 2026-11-07).
  seedChatListCacheForTest(sample);
  await invalidateChatListCache({ rowsRemoved: true });
  const made = { ...sample.today[0], id: "new" };
  const insert = (groups: ChatList) => ({ ...groups, today: [made, ...groups.today] });
  expect(updateChatListCache(insert)).toBeUndefined();
  expect(getCachedChatList()).toBeUndefined();
  expect(getCachedChat("c1")).toBeUndefined();
  let finish!: (value: ChatList) => void;
  listChats.mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
  const read = fetchChatList("token");
  expect(updateChatListCache(insert)).toBeUndefined();
  finish({ ...sample, today: [] });
  expect((await read).data?.today.map((chat) => chat.id)).toEqual(["new"]);
  expect(getCachedChat("c1")).toBeUndefined();
});

it("says the rows shown went with the list only for a change that removed them, until a read", async () => {
  await invalidateChatListCache();
  expect([isChatListDropped(), chatListRowsRemoved()]).toEqual([true, false]);
  await invalidateChatListCache({ rowsRemoved: true });
  expect([isChatListDropped(), chatListRowsRemoved()]).toEqual([true, true]);
  listChats.mockResolvedValueOnce(sample);
  await fetchChatList("token");
  expect([isChatListDropped(), chatListRowsRemoved()]).toEqual([false, false]);
  mockSession++;
  expect([isChatListDropped(), chatListRowsRemoved()]).toEqual([false, false]);
});

it("lets a chat deleted in Settings go as the drawer's delete does, keeping every other row", async () => {
  // Review: an archived chat open under Settings stayed on screen after it was deleted.
  seedChatListCacheForTest(sample);
  const newChat = jest.fn();
  const deleted = jest.fn();
  const stops = [setActiveChatIdGlobal("c1"), registerNewChat(newChat), onAppEvent("chatsDeleted", deleted)];
  await forgetDeletedChat("c1");
  stops.forEach((stop) => stop());
  expect(deleted).toHaveBeenCalledWith({ chatIds: ["c1"] });
  expect(newChat).toHaveBeenCalledWith({ force: true });
  expect([isChatListDropped(), chatListRowsRemoved()]).toEqual([true, false]);
});

it("does not return current cached history to a token from an old account", async () => {
  seedChatListCacheForTest(sample);
  const { requireTokenSession } = jest.requireMock("@/lib/auth") as { requireTokenSession: jest.Mock };
  requireTokenSession.mockImplementationOnce(() => { throw new Error("old account"); });
  expect(await fetchChatList("old-token")).toEqual({ data: null, error: expect.any(Error) });
  expect(getCachedChatList()).toEqual(sample);
});

describe("the list kept on disk", () => {
  const tokenFor = (sub: string) => {
    const encode = (value: unknown) => btoa(JSON.stringify(value)).replace(/=/g, "").replace(/\+/g, "-").replace(/\//g, "_");
    return `${encode({ alg: "HS256" })}.${encode({ sub })}.signature`;
  };
  const token = tokenFor("user-1");
  const idle = async () => {
    mockIdle.splice(0).forEach((task) => task());
    for (let i = 0; i < 10; i++) await Promise.resolve();
  };

  beforeEach(async () => {
    jest.clearAllMocks();
    mockSession = 0;
    await invalidateChatListCache();
    await idle();
    mockStored.clear();
  });

  it("paints the chats this account had last time until the list is read again", async () => {
    mockStored.set("user-1", sample);
    await expect(restoreChatList(token)).resolves.toBe(true);
    expect(getCachedChatList()).toEqual(sample);
    expect(getCachedChat("c1")?.title).toBe("Hello");
    // Its titles may be old: not fresh, not a read, and not the server's row.
    expect(isChatListFresh()).toBe(false);
    expect(getChatListFetchedAt()).toBeUndefined();
    expect(getFetchedChat("c1")).toBeUndefined();
    listChats.mockResolvedValueOnce(sample);
    await fetchChatList(token);
    expect(listChats).toHaveBeenCalledTimes(1);
    expect(getFetchedChat("c1")?.title).toBe("Hello");
  });

  it("restores nothing over a list already read, for another account, or for an old token", async () => {
    mockStored.set("user-2", sample);
    await expect(restoreChatList(token)).resolves.toBe(false);
    await invalidateChatListCache();
    mockStored.set("user-1", sample);
    const { requireTokenSession } = jest.requireMock("@/lib/auth") as { requireTokenSession: jest.Mock };
    requireTokenSession.mockImplementationOnce(() => { throw new Error("old account"); });
    await expect(restoreChatList(token)).resolves.toBe(false);
    await invalidateChatListCache();
    mockStored.set("user-1", sample);
    const read = { ...sample, today: [] };
    seedChatListCacheForTest(read);
    await expect(restoreChatList(token)).resolves.toBe(false);
    expect(getCachedChatList()).toEqual(read);
  });

  it("writes the list it read for this account once idle, and not after sign-out", async () => {
    listChats.mockResolvedValueOnce(sample);
    await fetchChatList(token);
    await idle();
    expect(writeStoredChatList).toHaveBeenCalledWith("user-1", sample);
    (writeStoredChatList as jest.Mock).mockClear();
    updateChatListCache((groups) => ({ ...groups, today: [] }));
    mockSession++;
    await idle();
    expect(writeStoredChatList).not.toHaveBeenCalled();
  });

  it("writes edits made to a restored list, but never a list of edits alone", async () => {
    // A new session, never read: the edit makes a list of its own.
    mockSession++;
    updateChatListCache((groups) => ({ ...groups, today: sample.today }));
    await idle();
    expect(writeStoredChatList).not.toHaveBeenCalled();
    await invalidateChatListCache();
    mockStored.set("user-1", sample);
    await restoreChatList(token);
    await idle();
    expect(writeStoredChatList).not.toHaveBeenCalled();
    updateChatListCache((groups) => ({ ...groups, today: [] }));
    await idle();
    expect(writeStoredChatList).toHaveBeenCalledWith("user-1", { ...sample, today: [] });
  });

  it("forgets the stored list with the cache", async () => {
    await invalidateChatListCache();
    expect(clearStoredChatList).toHaveBeenCalled();
  });
});

describe("older chats (CLAR-12)", () => {
  const row = (id: string) => ({ ...sample.today[0]!, id, title: id });
  const listOlderChats = api.listOlderChats as jest.Mock;
  beforeEach(() => { jest.clearAllMocks(); mockSession = 0; invalidateChatListCache(); });

  it("reads the page after the list's cursor and appends it", async () => {
    seedChatListCacheForTest({ ...sample, older: [row("o1")], next_cursor: "after-o1" });
    listOlderChats.mockResolvedValueOnce({ ...sample, today: [], older: [row("o2"), row("o1")], next_cursor: null });
    await fetchOlderChats("token");
    expect(listOlderChats).toHaveBeenCalledWith("token", "after-o1");
    const list = getCachedChatList();
    expect(list?.older.map((chat) => chat.id)).toEqual(["o1", "o2"]);
    expect(list?.next_cursor).toBeNull();
  });

  it("reads nothing once the list holds every chat", async () => {
    seedChatListCacheForTest(sample);
    expect(await fetchOlderChats("token")).toBeNull();
    expect(listOlderChats).not.toHaveBeenCalled();
  });

  it("drops a page a refresh overtook, and another account's page", async () => {
    seedChatListCacheForTest({ ...sample, next_cursor: "after-a" });
    let finish!: (value: ChatList) => void;
    listOlderChats.mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
    const reading = fetchOlderChats("token");
    seedChatListCacheForTest({ ...sample, next_cursor: "after-b" });
    finish({ ...sample, today: [], older: [row("stale")], next_cursor: null });
    await reading;
    expect(getCachedChatList()?.older).toEqual([]);

    seedChatListCacheForTest({ ...sample, next_cursor: "after-b" });
    listOlderChats.mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
    const late = fetchOlderChats("token");
    mockSession++;
    finish({ ...sample, today: [], older: [row("account-a")], next_cursor: null });
    expect(await late).toBeNull();
    expect(getCachedChatList()?.older ?? []).toEqual([]);

  });
});

describe("archived chats past the first page", () => {
  const row = (id: string) => ({ ...sample.today[0]!, id, title: id, archived: true });
  const listArchivedChats = api.listArchivedChats as jest.Mock;
  beforeEach(() => { jest.clearAllMocks(); mockSession = 0; invalidateChatListCache(); });

  it("reads the page after the archived cursor and appends it", async () => {
    seedChatListCacheForTest({ ...sample, archived: [row("a1")], archived_next_cursor: "after-a1" });
    listArchivedChats.mockResolvedValueOnce({ items: [row("a2")], next_cursor: null });
    await fetchMoreArchivedChats("token");
    expect(listArchivedChats).toHaveBeenCalledWith("token", "after-a1");
    expect(getCachedChatList()?.archived.map((chat) => chat.id)).toEqual(["a1", "a2"]);
    expect(getCachedChatList()?.archived_next_cursor).toBeNull();
  });

  it("reads nothing once every archived chat is listed", async () => {
    seedChatListCacheForTest(sample);
    expect(await fetchMoreArchivedChats("token")).toBeNull();
    expect(listArchivedChats).not.toHaveBeenCalled();
  });
});
