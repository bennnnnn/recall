import type { Chat, ChatList } from "@/lib/api";

/** Date buckets returned by GET /chats (matches backend RECENCY_BUCKETS). */
export const CHAT_DATE_SECTIONS = [
  "today",
  "yesterday",
  "last_7_days",
  "this_month",
  "older",
] as const;

export type ChatDateSection = (typeof CHAT_DATE_SECTIONS)[number];

export const PINNED_CHAT_SECTION = "pinned" as const;
export const ARCHIVED_CHAT_SECTION = "archived" as const;

export type ChatListSectionKey =
  | typeof PINNED_CHAT_SECTION
  | ChatDateSection
  | typeof ARCHIVED_CHAT_SECTION;

export function emptyChatList(): ChatList {
  return {
    pinned: [],
    today: [],
    yesterday: [],
    last_7_days: [],
    this_month: [],
    older: [],
    archived: [],
  };
}

export function chatsForSection(groups: ChatList, key: ChatListSectionKey): Chat[] {
  return groups[key];
}

export function activeChatsFromGroups(groups: ChatList): Chat[] {
  return [
    ...groups.pinned,
    ...groups.today,
    ...groups.yesterday,
    ...groups.last_7_days,
    ...groups.this_month,
    ...groups.older,
  ];
}

export function allChatsFromGroups(groups: ChatList): Chat[] {
  return [...activeChatsFromGroups(groups), ...groups.archived];
}

/** Drawer sections that can collapse (pinned stays open). */
export function isCollapsibleChatSection(key: ChatListSectionKey): boolean {
  return key !== PINNED_CHAT_SECTION;
}

export function defaultChatSectionCollapsed(key: ChatListSectionKey): boolean {
  if (key === PINNED_CHAT_SECTION || key === "today") {
    return false;
  }
  return true;
}

export function drawerSectionTitleKey(key: ChatListSectionKey): string {
  return `drawer.${key}`;
}

export function patchChatListGroups(
  groups: ChatList,
  chatId: string,
  patch: Partial<Chat>,
): ChatList {
  const apply = (list: Chat[]) =>
    list.map((c) => (c.id === chatId ? { ...c, ...patch } : c));
  return {
    pinned: apply(groups.pinned),
    today: apply(groups.today),
    yesterday: apply(groups.yesterday),
    last_7_days: apply(groups.last_7_days),
    this_month: apply(groups.this_month),
    older: apply(groups.older),
    archived: apply(groups.archived),
  };
}

export function removeChatFromGroups(groups: ChatList, chatId: string): ChatList {
  const drop = (list: Chat[]) => list.filter((c) => c.id !== chatId);
  return {
    pinned: drop(groups.pinned),
    today: drop(groups.today),
    yesterday: drop(groups.yesterday),
    last_7_days: drop(groups.last_7_days),
    this_month: drop(groups.this_month),
    older: drop(groups.older),
    archived: drop(groups.archived),
  };
}
