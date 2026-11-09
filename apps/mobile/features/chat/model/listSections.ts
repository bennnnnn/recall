import type { Chat, ChatList, Page } from "@/lib/api";

/** Date buckets returned by GET /chats (matches backend RECENCY_BUCKETS). */
export const CHAT_DATE_SECTIONS = [
  "today",
  "yesterday",
  "last_7_days",
  "this_month",
  "older",
] as const;

type ChatDateSection = (typeof CHAT_DATE_SECTIONS)[number];

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
    ...groups,
    pinned: drop(groups.pinned),
    today: drop(groups.today),
    yesterday: drop(groups.yesterday),
    last_7_days: drop(groups.last_7_days),
    this_month: drop(groups.this_month),
    older: drop(groups.older),
    archived: drop(groups.archived),
  };
}

/** The server's day buckets (`group_by_recency`), in the phone's zone, which its list reads send. */
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

const newestFirst = (a: Chat, b: Chat) =>
  Date.parse(b.updated_at) - Date.parse(a.updated_at) || b.id.localeCompare(a.id);

/**
 * The dated chats under the headings they have now, in the phone's zone. A list read
 * earlier keeps the day and zone it was grouped in: the disk copy a cold start paints
 * (written before a flight, or yesterday) and a list held in memory across midnight,
 * while the chats the phone inserts are filed by the day now. The same list back when
 * no chat moves.
 */
export function regroupChatsByRecency(groups: ChatList, now = new Date()): ChatList {
  const sections = Object.fromEntries(CHAT_DATE_SECTIONS.map((key) => [key, [] as Chat[]])) as
    Record<ChatDateSection, Chat[]>;
  let moved = false;
  for (const key of CHAT_DATE_SECTIONS) {
    for (const chat of groups[key]) {
      const section = chatRecencySection(chat, now);
      moved ||= section !== key;
      sections[section].push(chat);
    }
  }
  if (!moved) return groups;
  // Chats filed on different days can meet in one section out of order.
  for (const key of CHAT_DATE_SECTIONS) sections[key].sort(newestFirst);
  return { ...groups, ...sections };
}

/** A page of older dated chats joins the list below what it already shows (CLAR-12). */
export function appendOlderChats(groups: ChatList, older: ChatList): ChatList {
  const shown = new Set(allChatsFromGroups(groups).map((chat) => chat.id));
  const next: ChatList = { ...groups, next_cursor: older.next_cursor ?? null };
  for (const key of CHAT_DATE_SECTIONS) {
    next[key] = [...groups[key], ...older[key].filter((chat) => !shown.has(chat.id))];
  }
  return next;
}

/** A page of archived chats joins the archived section below what it already shows. */
export function appendArchivedChats(groups: ChatList, page: Page<Chat>): ChatList {
  const shown = new Set(groups.archived.map((chat) => chat.id));
  return {
    ...groups,
    archived: [...groups.archived, ...page.items.filter((chat) => !shown.has(chat.id))],
    archived_next_cursor: page.next_cursor ?? null,
  };
}

/** The same row: a chat edited since (renamed, written to) is not where the old page put it. */
const sameRow = (a: Chat) => (b: Chat) => a.id === b.id && a.updated_at === b.updated_at;

/**
 * The rows `shown` holds past the end of a fresh first page: those after the page's last row,
 * when `shown` holds that row unchanged (the page still leads into them), less any the page
 * holds itself. Null when the page is the whole list or no longer leads into the rows below.
 */
function rowsBelow<R extends { chat: Chat }>(shown: R[], page: R[], more: unknown, inPage: Set<string>): R[] | null {
  const last = page.at(-1);
  if (!more || !last) return null;
  const at = shown.findIndex((row) => sameRow(last.chat)(row.chat));
  if (at < 0) return null;
  const below = shown.slice(at + 1).filter((row) => !inPage.has(row.chat.id));
  return below.length ? below : null;
}

/**
 * A fresh first page over a list that read further (older dated chats, archived "Show
 * more"): it replaces only what it covers, and the pages read below it stay, with their
 * cursor. A re-read put the list back to its first page, under the user's thumb.
 */
export function keepLoadedPages(shown: ChatList, fresh: ChatList): ChatList {
  const inPage = new Set(allChatsFromGroups(fresh).map((chat) => chat.id));
  const dated = (groups: ChatList) => CHAT_DATE_SECTIONS.flatMap((key) => groups[key].map((chat) => ({ chat, key })));
  const next: ChatList = { ...fresh };
  const olderRows = rowsBelow(dated(shown), dated(fresh), fresh.next_cursor, inPage);
  if (olderRows) {
    for (const key of CHAT_DATE_SECTIONS) next[key] = [...fresh[key]];
    for (const { chat, key } of olderRows) next[key].push(chat);
    next.next_cursor = shown.next_cursor ?? null;
  }
  const archive = (groups: ChatList) => groups.archived.map((chat) => ({ chat }));
  const archivedRows = rowsBelow(archive(shown), archive(fresh), fresh.archived_next_cursor, inPage);
  if (archivedRows) {
    next.archived = [...fresh.archived, ...archivedRows.map(({ chat }) => chat)];
    next.archived_next_cursor = shown.archived_next_cursor ?? null;
  }
  return next;
}

export function insertChatByRecency(groups: ChatList, chat: Chat): ChatList {
  const key = chat.archived ? ARCHIVED_CHAT_SECTION : chat.pinned ? PINNED_CHAT_SECTION : chatRecencySection(chat);
  return { ...groups, [key]: [...groups[key], chat].sort(newestFirst) };
}
