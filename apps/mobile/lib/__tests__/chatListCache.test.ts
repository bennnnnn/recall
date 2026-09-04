import { api } from "@/lib/api";
import {
  fetchChatList,
  getCachedChat,
  getCachedChatList,
  consumeCreatedSuggestionSkip,
  peekCreatedChat,
  rememberCreatedChat,
  getChatListFetchedAt,
  invalidateChatListCache,
  isChatListFresh,
  prefetchChatList,
  setChatListCache,
  updateChatListCache,
} from "@/lib/cache/chatListCache";
import {
  markChatHasAssistant,
  shouldProbePreviousChat,
} from "@/lib/chatDraftLogic";
import type { ChatList } from "@/lib/api";

jest.mock("@/lib/api", () => ({
  api: {
    listChats: jest.fn(),
  },
}));

let mockSession = 0;
jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => mockSession, requireTokenSession: jest.fn() }));
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
    setChatListCache(sample);
    expect(isChatListFresh()).toBe(true);
    expect(getCachedChatList()).toEqual(sample);
    expect(getChatListFetchedAt()).toEqual(expect.any(Number));

    const result = await fetchChatList("token");
    expect(result).toEqual(sample);
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
    expect(a).toEqual(sample);
    expect(b).toEqual(sample);
    expect(listChats).toHaveBeenCalledTimes(1);
  });

  it("remembers the POST /chats body until logout invalidates", () => {
    rememberCreatedChat(sample.today[0]);
    expect(peekCreatedChat("c1")?.title).toBe("Hello");
    expect(peekCreatedChat("other")).toBeUndefined();
    expect(consumeCreatedSuggestionSkip("c1")).toBe(true);
    expect(consumeCreatedSuggestionSkip("c1")).toBe(false);
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
    setChatListCache({
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

  it("prefetch skips when cache is already fresh", () => {
    setChatListCache(sample);
    prefetchChatList("token");
    expect(listChats).not.toHaveBeenCalled();
  });

  it("normalizes missing archived to an empty array", async () => {
    const { archived: _omit, ...withoutArchived } = sample;
    listChats.mockResolvedValue(withoutArchived);
    const result = await fetchChatList("token", { force: true });
    expect(result?.archived).toEqual([]);
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
  expect(await old).toBeNull();
  expect(getCachedChatList()).toEqual(newList);
});

it("isolates cached rows, created chat and inflight requests by account session", async () => {
  invalidateChatListCache();
  setChatListCache(sample);
  rememberCreatedChat(sample.today[0]);
  let finish!: (value: ChatList) => void;
  listChats.mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
  const old = fetchChatList("token", { force: true });
  mockSession++;
  expect(getCachedChatList()).toBeUndefined();
  expect(peekCreatedChat("c1")).toBeUndefined();
  expect(consumeCreatedSuggestionSkip("c1")).toBe(false);
  finish(sample);
  expect(await old).toBeNull();
  expect(getCachedChatList()).toBeUndefined();
});

it("replays local edits on a late list response while retaining other server rows", async () => {
  invalidateChatListCache();
  setChatListCache(sample);
  let finish!: (value: ChatList) => void;
  listChats.mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
  const read = fetchChatList("token", { force: true });
  updateChatListCache((groups) => ({ ...groups, today: groups.today.filter((chat) => chat.id !== "c1") }));
  const incoming = { ...sample, today: [...sample.today, { ...sample.today[0], id: "server-new" }] };
  finish(incoming);
  expect((await read)?.today.map((chat) => chat.id)).toEqual(["server-new"]);
  expect(getCachedChat("c1")).toBeUndefined();
});

it("keeps optimistic first-chat insertion from suppressing the first full list read", async () => {
  invalidateChatListCache();
  updateChatListCache((groups) => ({ ...groups, today: sample.today }));
  expect(isChatListFresh()).toBe(false);
  listChats.mockResolvedValueOnce(sample);
  await fetchChatList("token");
  expect(isChatListFresh()).toBe(true);
});


it("does not return current cached history to a token from an old account", async () => {
  setChatListCache(sample);
  const { requireTokenSession } = jest.requireMock("@/lib/auth") as { requireTokenSession: jest.Mock };
  requireTokenSession.mockImplementationOnce(() => { throw new Error("old account"); });
  expect(await fetchChatList("old-token")).toBeNull();
  expect(getCachedChatList()).toEqual(sample);
});
