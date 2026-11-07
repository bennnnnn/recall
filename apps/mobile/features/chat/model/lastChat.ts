import type { Chat, ChatList } from "@/lib/api";

/**
 * The chat the user was last in, for the home's "pick up where you left off": the most
 * recently active titled chat other than the one on screen. An untitled chat has no reply
 * yet, and an archived one was put away.
 */
export function lastChat(list: ChatList | undefined, openId: string | null): Chat | null {
  if (!list) return null;
  const chats = [
    ...list.pinned,
    ...list.today,
    ...list.yesterday,
    ...list.last_7_days,
    ...list.this_month,
    ...list.older,
  ];
  let last: Chat | null = null;
  for (const chat of chats) {
    if (!chat.title?.trim() || chat.archived || chat.id === openId) continue;
    if (!last || chat.updated_at > last.updated_at) last = chat;
  }
  return last;
}
