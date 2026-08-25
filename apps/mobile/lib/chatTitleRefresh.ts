import type { Chat } from "@/lib/api";

export type FirstReplyTitlePlan = {
  insert: Chat | null;
  fetch: boolean;
  poll: boolean;
};

/**
 * First assistant reply used to GET /chats/{id} just to insert the drawer row.
 * Home send already has the POST /chats body; a titled drawer row is enough.
 */
export function firstReplyTitlePlan(
  created: Chat | undefined,
  listed: Chat | undefined,
): FirstReplyTitlePlan {
  const chat = created ?? listed;
  if (!chat) return { insert: null, fetch: true, poll: true };
  return { insert: chat, fetch: false, poll: !chat.title };
}
