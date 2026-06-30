import { messageListItemType, ESTIMATED_MESSAGE_HEIGHT } from "@/lib/messageListLayout";

describe("messageListLayout", () => {
  it("uses a stable streaming item type", () => {
    expect(messageListItemType({ id: "streaming", role: "assistant" })).toBe("streaming");
    expect(messageListItemType({ id: "msg-1", role: "assistant" })).toBe("assistant");
    expect(messageListItemType({ id: "msg-2", role: "user" })).toBe("user");
  });

  it("exports a reasonable default height hint", () => {
    expect(ESTIMATED_MESSAGE_HEIGHT).toBeGreaterThan(40);
    expect(ESTIMATED_MESSAGE_HEIGHT).toBeLessThan(200);
  });
});
