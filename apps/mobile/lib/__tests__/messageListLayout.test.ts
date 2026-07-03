import { messageListItemType, messageListKey, ESTIMATED_MESSAGE_HEIGHT } from "@/lib/messageListLayout";

describe("messageListLayout", () => {
  it("uses role for FlashList item type", () => {
    expect(messageListItemType({ id: "streaming", role: "assistant" })).toBe("assistant");
    expect(messageListItemType({ id: "msg-1", role: "assistant" })).toBe("assistant");
    expect(messageListItemType({ id: "msg-2", role: "user" })).toBe("user");
  });

  it("prefers renderKey for FlashList identity", () => {
    expect(messageListKey({ id: "streaming", renderKey: "stream-1" })).toBe("stream-1");
    expect(messageListKey({ id: "msg-1" })).toBe("msg-1");
  });

  it("exports a reasonable default height hint", () => {
    expect(ESTIMATED_MESSAGE_HEIGHT).toBeGreaterThan(40);
    expect(ESTIMATED_MESSAGE_HEIGHT).toBeLessThan(200);
  });
});
