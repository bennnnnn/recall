import {
  resolveActiveChatId,
  shouldPreCreateDraft,
  shouldWarmDraftSocket,
} from "@/lib/chatDraftLogic";

describe("chatDraftLogic", () => {
  it("resolveActiveChatId prefers committed chat over draft", () => {
    expect(resolveActiveChatId("chat-1", "draft-1")).toBe("chat-1");
    expect(resolveActiveChatId(null, "draft-1")).toBe("draft-1");
    expect(resolveActiveChatId(null, null)).toBeNull();
  });

  it("shouldPreCreateDraft only on empty home with token", () => {
    expect(
      shouldPreCreateDraft({
        token: "tok",
        routeChatId: undefined,
        chatId: null,
        messagesLength: 0,
        streaming: false,
      }),
    ).toBe(true);
    expect(
      shouldPreCreateDraft({
        token: null,
        routeChatId: undefined,
        chatId: null,
        messagesLength: 0,
        streaming: false,
      }),
    ).toBe(false);
    expect(
      shouldPreCreateDraft({
        token: "tok",
        routeChatId: "existing",
        chatId: null,
        messagesLength: 0,
        streaming: false,
      }),
    ).toBe(false);
    expect(
      shouldPreCreateDraft({
        token: "tok",
        routeChatId: undefined,
        chatId: "chat-1",
        messagesLength: 0,
        streaming: false,
      }),
    ).toBe(false);
    expect(
      shouldPreCreateDraft({
        token: "tok",
        routeChatId: undefined,
        chatId: null,
        messagesLength: 2,
        streaming: false,
      }),
    ).toBe(false);
    expect(
      shouldPreCreateDraft({
        token: "tok",
        routeChatId: undefined,
        chatId: null,
        messagesLength: 0,
        streaming: true,
      }),
    ).toBe(false);
  });

  it("shouldWarmDraftSocket when draft exists and chat not committed", () => {
    expect(
      shouldWarmDraftSocket({
        token: "tok",
        draftChatId: "draft-1",
        chatId: null,
        streaming: false,
      }),
    ).toBe(true);
    expect(
      shouldWarmDraftSocket({
        token: "tok",
        draftChatId: "draft-1",
        chatId: "chat-1",
        streaming: false,
      }),
    ).toBe(false);
    expect(
      shouldWarmDraftSocket({
        token: null,
        draftChatId: "draft-1",
        chatId: null,
        streaming: false,
      }),
    ).toBe(false);
  });
});
