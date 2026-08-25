import type { Chat } from "@/lib/api";

export type FirstReplyTitlePlan = {
  insert: Chat | null;
  fetch: boolean;
};

/**
 * First assistant reply used to GET /chats/{id} just to insert the drawer row.
 * Home send already has the POST /chats body. Do not title-poll on send —
 * the header stays untitled until the next list refresh.
 */
export function firstReplyTitlePlan(
  created: Chat | undefined,
  listed: Chat | undefined,
): FirstReplyTitlePlan {
  const chat = created ?? listed;
  if (!chat) return { insert: null, fetch: true };
  return { insert: chat, fetch: false };
}
