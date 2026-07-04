import {
  messageListItemType,
  messageListKey,
  ESTIMATED_MESSAGE_HEIGHT,
} from "@/lib/messageListLayout";

describe("messageListLayout", () => {
  it("uses role for user rows", () => {
    expect(messageListItemType({ id: "msg-2", role: "user" })).toBe("user");
  });

  it("distinguishes assistant row layouts by fenced content", () => {
    expect(messageListItemType({ id: "streaming", role: "assistant" })).toBe("assistant");
    expect(
      messageListItemType({
        id: "msg-quiz",
        role: "assistant",
        content: "```vocab_quiz\n{\"word\":\"hola\"}\n```",
      }),
    ).toBe("assistant-quiz");
    expect(
      messageListItemType({
        id: "msg-vocab",
        role: "assistant",
        content: "```vocab_card\n{\"word\":\"hola\",\"definition\":\"hello\"}\n```",
      }),
    ).toBe("assistant-vocab");
    expect(
      messageListItemType({
        id: "msg-cal",
        role: "assistant",
        content: '```calendar_proposal\n{"title":"Standup"}\n```',
      }),
    ).toBe("assistant-calendar");
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
