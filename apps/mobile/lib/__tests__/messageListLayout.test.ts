import {
  beginStreamLayoutHold,
  isFreshStreamRenderKey,
  messageListItemType,
  messageListKey,
  ESTIMATED_MESSAGE_HEIGHT,
  STREAM_AUTOSCROLL_RESUME_MS,
  STREAM_LAYOUT_SETTLE_MS,
  shouldHoldStreamLayoutOnPersistedMount,
  shouldStartRenderingFromBottom,
} from "@/lib/messageListLayout";

describe("messageListLayout", () => {
  it("keeps the first turn under the header", () => {
    expect(
      shouldStartRenderingFromBottom({ messageCount: 0, hasMoreOlder: false }),
    ).toBe(false);
    expect(
      shouldStartRenderingFromBottom({ messageCount: 1, hasMoreOlder: false }),
    ).toBe(false);
    expect(
      shouldStartRenderingFromBottom({ messageCount: 2, hasMoreOlder: false }),
    ).toBe(false);
    expect(
      shouldStartRenderingFromBottom({ messageCount: 3, hasMoreOlder: false }),
    ).toBe(true);
    expect(
      shouldStartRenderingFromBottom({ messageCount: 1, hasMoreOlder: true }),
    ).toBe(true);
  });

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

  it("detects fresh stream render keys", () => {
    expect(isFreshStreamRenderKey("stream-171")).toBe(true);
    expect(isFreshStreamRenderKey("msg-1")).toBe(false);
    expect(isFreshStreamRenderKey(undefined)).toBe(false);
  });

  it("keeps native autoscroll suppressed past the chrome settle tick", () => {
    expect(STREAM_AUTOSCROLL_RESUME_MS).toBeGreaterThan(STREAM_LAYOUT_SETTLE_MS);
  });

  it("beginStreamLayoutHold honors a longer resume delay", () => {
    jest.useFakeTimers();
    const setHeld = jest.fn();
    const cleanup = beginStreamLayoutHold(setHeld, STREAM_AUTOSCROLL_RESUME_MS);
    expect(setHeld).toHaveBeenCalledWith(true);
    jest.advanceTimersByTime(STREAM_LAYOUT_SETTLE_MS);
    expect(setHeld).not.toHaveBeenCalledWith(false);
    jest.advanceTimersByTime(STREAM_AUTOSCROLL_RESUME_MS - STREAM_LAYOUT_SETTLE_MS);
    expect(setHeld).toHaveBeenCalledWith(false);
    cleanup();
    jest.useRealTimers();
  });

  it("shouldHoldStreamLayoutOnPersistedMount only for fresh assistant rows", () => {
    expect(
      shouldHoldStreamLayoutOnPersistedMount({
        isUser: false,
        isGenerating: false,
        renderKey: "stream-1",
        alreadyApplied: false,
      }),
    ).toBe(true);
    expect(
      shouldHoldStreamLayoutOnPersistedMount({
        isUser: true,
        isGenerating: false,
        renderKey: "stream-1",
        alreadyApplied: false,
      }),
    ).toBe(false);
    expect(
      shouldHoldStreamLayoutOnPersistedMount({
        isUser: false,
        isGenerating: true,
        renderKey: "stream-1",
        alreadyApplied: false,
      }),
    ).toBe(false);
    expect(
      shouldHoldStreamLayoutOnPersistedMount({
        isUser: false,
        isGenerating: false,
        renderKey: "stream-1",
        alreadyApplied: true,
      }),
    ).toBe(false);
  });
});
