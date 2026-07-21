import { applyOptimisticEdit, shouldRestoreEditOnError } from "@/lib/chatEditLogic";
import type { Message } from "@/lib/api";

const user1: Message = {
  id: "u1",
  role: "user",
  content: "first",
  model: null,
  created_at: "2026-01-01T00:00:00Z",
};
const a1: Message = {
  id: "a1",
  role: "assistant",
  content: "reply1",
  model: null,
  created_at: "2026-01-01T00:00:01Z",
};
const user2: Message = {
  id: "u2",
  role: "user",
  content: "second",
  model: null,
  created_at: "2026-01-01T00:00:02Z",
};
const a2: Message = {
  id: "a2",
  role: "assistant",
  content: "reply2",
  model: null,
  created_at: "2026-01-01T00:00:03Z",
};

describe("chatEditLogic", () => {
  it("applyOptimisticEdit truncates after the edited turn", () => {
    const { snapshot, messages } = applyOptimisticEdit(
      [user1, a1, user2, a2],
      "u2",
      "edited second",
      "local-edit-1",
    );
    expect(snapshot).toEqual([user1, a1, user2, a2]);
    expect(messages).toHaveLength(3);
    expect(messages[0]).toBe(user1);
    expect(messages[1]).toBe(a1);
    expect(messages[2]).toMatchObject({
      id: "local-edit-1",
      role: "user",
      content: "edited second",
    });
  });

  it("applyOptimisticEdit is a no-op for unknown message ids", () => {
    const thread = [user1, a1];
    const { snapshot, messages } = applyOptimisticEdit(
      thread,
      "missing",
      "x",
      "local-edit-1",
    );
    expect(snapshot).toBe(thread);
    expect(messages).toBe(thread);
  });

  it("shouldRestoreEditOnError is true only when a snapshot exists", () => {
    expect(shouldRestoreEditOnError(true)).toBe(true);
    expect(shouldRestoreEditOnError(false)).toBe(false);
  });
});
