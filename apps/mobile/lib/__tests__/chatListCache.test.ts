import { api } from "@/lib/api";
import {
  fetchChatList,
  getCachedChatList,
  getChatListFetchedAt,
  invalidateChatListCache,
  isChatListFresh,
  prefetchChatList,
  setChatListCache,
} from "@/lib/chatListCache";
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
