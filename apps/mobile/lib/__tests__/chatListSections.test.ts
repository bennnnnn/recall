import {
  activeChatsFromGroups,
  defaultChatSectionCollapsed,
  drawerSectionTitleKey,
  emptyChatList,
  isCollapsibleChatSection,
  PINNED_CHAT_SECTION,
} from "@/lib/chatListSections";

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
