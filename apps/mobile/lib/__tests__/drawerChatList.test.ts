import { drawerChatFetchMode, insertChatIntoGroups } from "@/lib/drawerChatList";
import { removeChatFromGroups } from "@/lib/chatListSections";
import type { Chat, ChatList } from "@/lib/api";

const empty: ChatList = {
  pinned: [],
  today: [],
  yesterday: [],
  last_7_days: [],
  this_month: [],
  older: [],
  archived: [],
};

function chat(id: string, overrides: Partial<Chat> = {}): Chat {
  return {
    id,
    title: null,
    model: "free-chat",
    pinned: false,
    created_at: "2026-07-01T12:00:00Z",
    updated_at: "2026-07-01T12:00:00Z",
    ...overrides,
  };
}

describe("drawerChatFetchMode", () => {
  const base = {
    isDrawerOpen: true,
    hasToken: true,
    hasLoadedOnce: false,
    lastFetchedAt: 0,
    chatCount: 0,
    now: 100_000,
    staleMs: 20_000,
  };

  it("skips spinner path while the drawer is closed (idle warm is separate)", () => {
    expect(drawerChatFetchMode({ ...base, isDrawerOpen: false })).toBe("skip");
  });

  it("full-fetches on first open", () => {
    expect(drawerChatFetchMode(base)).toBe("full");
  });

  it("background-refreshes when open and stale", () => {
    expect(
      drawerChatFetchMode({
        ...base,
        hasLoadedOnce: true,
        lastFetchedAt: 50_000,
        chatCount: 3,
      }),
    ).toBe("background");
  });

  it("skips when open and fresh", () => {
    expect(
      drawerChatFetchMode({
        ...base,
        hasLoadedOnce: true,
        lastFetchedAt: 90_000,
        chatCount: 3,
      }),
    ).toBe("skip");
  });
});

describe("insertChatIntoGroups", () => {
  it("adds a new chat to today", () => {
    const next = insertChatIntoGroups(empty, chat("a"));
    expect(next.today.map((c) => c.id)).toEqual(["a"]);
  });

  it("does not duplicate an existing chat", () => {
    const groups: ChatList = { ...empty, today: [chat("a")] };
    const next = insertChatIntoGroups(groups, chat("a", { title: "Renamed" }));
    expect(next).toBe(groups);
    expect(next.today).toHaveLength(1);
  });

  it("adds pinned chats to pinned", () => {
    const next = insertChatIntoGroups(empty, chat("p", { pinned: true }));
    expect(next.pinned.map((c) => c.id)).toEqual(["p"]);
    expect(next.today).toHaveLength(0);
  });

  it("adds archived chats to archived", () => {
    const next = insertChatIntoGroups(empty, chat("z", { archived: true }));
    expect(next.archived.map((c) => c.id)).toEqual(["z"]);
  });
});

describe("archive/unarchive move (remove + reinsert with flipped field)", () => {
  it("moves an active chat into archived", () => {
    const groups: ChatList = { ...empty, today: [chat("a")] };
    const removed = removeChatFromGroups(groups, "a");
    const next = insertChatIntoGroups(removed, { ...chat("a"), archived: true });
    expect(next.today).toHaveLength(0);
    expect(next.archived.map((c) => c.id)).toEqual(["a"]);
  });

  it("moves an archived chat back to today when unarchived", () => {
    const groups: ChatList = { ...empty, archived: [chat("a", { archived: true })] };
    const removed = removeChatFromGroups(groups, "a");
    const next = insertChatIntoGroups(removed, { ...chat("a"), archived: false });
    expect(next.archived).toHaveLength(0);
    expect(next.today.map((c) => c.id)).toEqual(["a"]);
  });

  it("moves an archived pinned chat back to pinned when unarchived", () => {
    const groups: ChatList = {
      ...empty,
      archived: [chat("a", { archived: true, pinned: true })],
    };
    const removed = removeChatFromGroups(groups, "a");
    const next = insertChatIntoGroups(removed, { ...chat("a"), archived: false, pinned: true });
    expect(next.archived).toHaveLength(0);
    expect(next.pinned.map((c) => c.id)).toEqual(["a"]);
  });
});
