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
  const chat = allChatsFromGroups(groups).find((row) => row.id === chatId);
  if (!chat) return groups;
  const updated = { ...chat, ...patch };
  if (patch.archived === true) updated.pinned = false;
  if (updated.pinned !== chat.pinned || updated.archived !== chat.archived || updated.updated_at !== chat.updated_at) {
    return insertChatByRecency(removeChatFromGroups(groups, chatId), updated);
  }
  const next = { ...groups };
  for (const key of [PINNED_CHAT_SECTION, ...CHAT_DATE_SECTIONS, ARCHIVED_CHAT_SECTION]) {
    next[key] = groups[key].map((row) => row.id === chatId ? updated : row);
  }
  return next;
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

/** Matches server recency buckets using the device timezone synced to the account. */
export function chatRecencySection(chat: Chat, now = new Date()): ChatDateSection {
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today); yesterday.setDate(today.getDate() - 1);
  const week = new Date(today); week.setDate(today.getDate() - 7);
  const month = new Date(now.getFullYear(), now.getMonth(), 1);
  const updated = new Date(chat.updated_at).getTime();
  if (updated >= today.getTime()) return "today";
  if (updated >= yesterday.getTime()) return "yesterday";
  if (updated >= week.getTime()) return "last_7_days";
  if (updated >= month.getTime()) return "this_month";
  return "older";
}

export function insertChatByRecency(groups: ChatList, chat: Chat): ChatList {
  const key = chat.archived ? ARCHIVED_CHAT_SECTION : chat.pinned ? PINNED_CHAT_SECTION : chatRecencySection(chat);
  const rows = [...groups[key], chat].sort((a, b) =>
    Date.parse(b.updated_at) - Date.parse(a.updated_at) || b.id.localeCompare(a.id));
  return { ...groups, [key]: rows };
}
