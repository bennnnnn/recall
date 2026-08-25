import { firstReplyTitlePlan } from "@/lib/chatTitleRefresh";
import type { Chat } from "@/lib/api";

function chat(id: string, title: string | null): Chat {
  return {
    id,
    title,
    model: "free-chat",
    pinned: false,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  };
}

describe("firstReplyTitlePlan", () => {
  it("uses the POST /chats body so Home send skips GET /chats/{id}", () => {
    const created = chat("new", null);
    expect(firstReplyTitlePlan(created, undefined)).toEqual({
      insert: created,
      fetch: false,
      poll: true,
    });
  });

  it("skips fetch and poll when the drawer row already has a title", () => {
    const listed = chat("old", "Homework");
    expect(firstReplyTitlePlan(undefined, listed)).toEqual({
      insert: listed,
      fetch: false,
      poll: false,
    });
  });

  it("falls back to GET only when nothing is cached", () => {
    expect(firstReplyTitlePlan(undefined, undefined)).toEqual({
      insert: null,
      fetch: true,
      poll: true,
    });
  });
});
