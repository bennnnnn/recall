import type { Chat, ChatList } from "@/lib/api";
import { lastChat } from "@/features/chat/model/lastChat";

const chat = (id: string, updated: string, extra: Partial<Chat> = {}): Chat => ({
  id,
  title: `Chat ${id}`,
  model: "auto",
  pinned: false,
  created_at: updated,
  updated_at: updated,
  ...extra,
});

const list = (groups: Partial<ChatList>): ChatList => ({
  pinned: [],
  today: [],
  yesterday: [],
  last_7_days: [],
  this_month: [],
  older: [],
  archived: [],
  ...groups,
});

it("is the most recently active chat, a pinned one included", () => {
  const chats = list({
    pinned: [chat("p", "2026-11-06T09:00:00Z", { pinned: true })],
    today: [chat("t", "2026-11-06T08:00:00Z")],
    yesterday: [chat("y", "2026-11-05T20:00:00Z")],
  });
  expect(lastChat(chats, null)?.id).toBe("p");
});

it("skips the chat on screen, an untitled one and an archived one", () => {
  const chats = list({
    today: [
      chat("open", "2026-11-06T10:00:00Z"),
      chat("new", "2026-11-06T09:30:00Z", { title: null }),
      chat("away", "2026-11-06T09:00:00Z", { archived: true }),
      chat("last", "2026-11-06T08:00:00Z"),
    ],
  });
  expect(lastChat(chats, "open")?.id).toBe("last");
});

it("is nothing before the list is in, or with no chat yet", () => {
  expect(lastChat(undefined, null)).toBeNull();
  expect(lastChat(list({}), null)).toBeNull();
});
