import type { Chat } from "@/lib/api";
import { provisionalChatTitle } from "@/lib/chat/chatTitle";

export type FirstReplyTitlePlan = {
  insert: Chat | null;
  fetch: boolean;
  poll: boolean;
};

/** New chat closes the per-chat socket, so stream `done` never inserts the row. */
export function shouldInsertDrawerRowOnLeave(
  messages: readonly { role: string }[],
): boolean {
  return messages.some((m) => m.role === "user");
}

/**
 * First assistant reply used to GET /chats/{id} just to insert the drawer row.
 * Home send already has the POST /chats body. Use the first user line as the
 * title so we do not poll — the topic job still writes the server title later.
 */
export function firstReplyTitlePlan(
  created: Chat | undefined,
  listed: Chat | undefined,
  firstUserText?: string,
): FirstReplyTitlePlan {
  const chat = created ?? listed;
  const title = chat?.title || provisionalChatTitle(firstUserText);
  if (!chat) return { insert: null, fetch: !title, poll: !title };
  return {
    insert: title ? { ...chat, title } : chat,
    fetch: false,
    // POST /chats already inserted the row — do not poll while the topic job runs.
    poll: false,
  };
}
