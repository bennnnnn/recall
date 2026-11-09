import {
  activeChatsFromGroups,
  appendArchivedChats,
  appendOlderChats,
  defaultChatSectionCollapsed,
  drawerSectionTitleKey,
  emptyChatList,
  isCollapsibleChatSection,
  keepLoadedPages,
  PINNED_CHAT_SECTION,
  removeChatFromGroups,
} from "@/features/chat/model/listSections";

describe("chatListSections", () => {
  it("emptyChatList has all buckets", () => {
    expect(emptyChatList()).toEqual({
      pinned: [],
      today: [],
      yesterday: [],
      last_7_days: [],
      this_month: [],
      older: [],
      archived: [],
    });
  });

  it("activeChatsFromGroups excludes archived", () => {
    const groups = emptyChatList();
    groups.archived.push({
      id: "a",
      title: null,
      model: "free-chat",
      pinned: false,
      archived: true,
      created_at: "",
      updated_at: "",
    });
    groups.today.push({
      id: "t",
      title: null,
      model: "free-chat",
      pinned: false,
      created_at: "",
      updated_at: "",
    });
    expect(activeChatsFromGroups(groups).map((c) => c.id)).toEqual(["t"]);
  });

  it("pinned is not collapsible; only today starts expanded", () => {
    expect(isCollapsibleChatSection(PINNED_CHAT_SECTION)).toBe(false);
    expect(defaultChatSectionCollapsed("today")).toBe(false);
    expect(defaultChatSectionCollapsed("yesterday")).toBe(true);
    expect(defaultChatSectionCollapsed("last_7_days")).toBe(true);
    expect(defaultChatSectionCollapsed("older")).toBe(true);
  });

  it("drawerSectionTitleKey maps to i18n keys", () => {
    expect(drawerSectionTitleKey("last_7_days")).toBe("drawer.last_7_days");
  });
});


describe("older chat pages (CLAR-12)", () => {
  const chat = (id: string) => ({ id, title: id, model: "free-chat", pinned: false, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" });

  it("appends each dated group below what is shown, once, and takes the page's cursor", () => {
    const shown = { ...emptyChatList(), pinned: [chat("p")], older: [chat("a")], next_cursor: "after-a" };
    const page = { ...emptyChatList(), older: [chat("a"), chat("b")], next_cursor: "after-b" };
    const merged = appendOlderChats(shown, page);
    expect(merged.older.map((row) => row.id)).toEqual(["a", "b"]);
    expect(merged.pinned.map((row) => row.id)).toEqual(["p"]);
    expect(merged.next_cursor).toBe("after-b");
  });

  it("keeps the cursor when a chat leaves the list", () => {
    const groups = { ...emptyChatList(), older: [chat("a")], next_cursor: "after-a" };
    expect(removeChatFromGroups(groups, "a").next_cursor).toBe("after-a");
  });

  it("appends a page of archived chats below the ones shown, with the next cursor", () => {
    const shown = { ...emptyChatList(), archived: [chat("a")], archived_next_cursor: "after-a" };
    const merged = appendArchivedChats(shown, { items: [chat("a"), chat("b")], next_cursor: null });
    expect(merged.archived.map((row) => row.id)).toEqual(["a", "b"]);
    expect(merged.archived_next_cursor).toBeNull();
  });
});

describe("keepLoadedPages", () => {
  const row = (id: string, updated = "2026-01-01T00:00:00Z") =>
    ({ id, title: id, model: "free-chat", pinned: false, created_at: updated, updated_at: updated });
  const page1 = { ...emptyChatList(), today: [row("new")], older: [row("b"), row("c")], next_cursor: "after-c" };
  // The drawer read the first page, then one page of older chats and one of archived chats.
  const shown = {
    ...page1,
    older: [row("b"), row("c"), row("d"), row("e")],
    next_cursor: null,
    archived: [row("a1"), row("a2"), row("a3")],
    archived_next_cursor: "after-a3",
  };

  it("keeps the older and archived pages read below a first page that still leads into them", () => {
    const fresh = {
      ...page1, today: [row("newest", "2026-01-02T00:00:00Z"), row("new")],
      archived: [row("a1"), row("a2")], archived_next_cursor: "after-a2",
    };
    const merged = keepLoadedPages(shown, fresh);
    expect(merged.today.map((chat) => chat.id)).toEqual(["newest", "new"]);
    expect(merged.older.map((chat) => chat.id)).toEqual(["b", "c", "d", "e"]);
    expect(merged.next_cursor).toBeNull();
    expect(merged.archived.map((chat) => chat.id)).toEqual(["a1", "a2", "a3"]);
    expect(merged.archived_next_cursor).toBe("after-a3");
  });

  it("takes a row the first page holds now from the page, not from below", () => {
    const fresh = { ...page1, today: [row("d", "2026-01-03T00:00:00Z"), row("new")] };
    const merged = keepLoadedPages(shown, fresh);
    expect(merged.today.map((chat) => chat.id)).toEqual(["d", "new"]);
    expect(merged.older.map((chat) => chat.id)).toEqual(["b", "c", "e"]);
  });

  it("is the first page alone when it no longer leads into the rows below, or holds the whole list", () => {
    // More new chats than a page: its last row is not one the list holds, and its cursor reads on.
    const pushed = { ...emptyChatList(), today: [row("n1"), row("n2")], next_cursor: "after-n2" };
    expect(keepLoadedPages(shown, pushed)).toEqual(pushed);
    const whole = { ...emptyChatList(), today: [row("new")], older: [row("b")], next_cursor: null };
    expect(keepLoadedPages(shown, whole)).toEqual(whole);
  });
});
