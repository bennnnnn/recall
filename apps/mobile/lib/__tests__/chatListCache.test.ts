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
