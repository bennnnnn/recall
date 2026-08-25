import {
  resolveActiveChatId,
  shareEmptyChatCheck,
  shouldDiscardOnNewChat,
  shouldProbeEmptyChat,
  shouldProbePreviousChat,
  shouldWarmDraftSocket,
  markChatHasAssistant,
  clearKnownAssistantChats,
} from "@/lib/chatDraftLogic";

describe("chatDraftLogic", () => {
  it("shouldDiscardOnNewChat only when the route effect will not", () => {
    expect(shouldDiscardOnNewChat(undefined)).toBe(true);
    expect(shouldDiscardOnNewChat("chat-1")).toBe(false);
  });

  it("shareEmptyChatCheck coalesces overlapping runs for the same chat", async () => {
    let runs = 0;
    const run = () =>
      new Promise<void>((resolve) => {
        runs += 1;
        setTimeout(resolve, 20);
      });
    await Promise.all([
      shareEmptyChatCheck("c1", run),
      shareEmptyChatCheck("c1", run),
    ]);
    expect(runs).toBe(1);
    await shareEmptyChatCheck("c1", run);
    expect(runs).toBe(2);
  });

  it("resolveActiveChatId prefers committed chat over draft", () => {
    expect(resolveActiveChatId("chat-1", "draft-1")).toBe("chat-1");
    expect(resolveActiveChatId(null, "draft-1")).toBe("draft-1");
    expect(resolveActiveChatId(null, null)).toBeNull();
  });

  it("shouldProbeEmptyChat skips when the thread already has a reply", () => {
    expect(shouldProbeEmptyChat(true)).toBe(false);
    expect(shouldProbeEmptyChat(false)).toBe(true);
  });

  it("shouldProbePreviousChat skips after New chat clears the message list", () => {
    clearKnownAssistantChats();
    markChatHasAssistant("chat-1");
    expect(
      shouldProbePreviousChat({ chatId: "chat-1", messagesHadAssistant: false }),
    ).toBe(false);
    expect(
      shouldProbePreviousChat({ chatId: "chat-2", messagesHadAssistant: false }),
    ).toBe(true);
    clearKnownAssistantChats();
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
