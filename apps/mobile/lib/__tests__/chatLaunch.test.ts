import { queueChatLaunch, takeQueuedChatLaunch } from "@/lib/chatLaunch";

describe("chatLaunch", () => {
  beforeEach(() => {
    while (takeQueuedChatLaunch()) {
      /* drain */
    }
  });

  it("returns false for blank prompts", () => {
    expect(queueChatLaunch("   ")).toBe(false);
    expect(takeQueuedChatLaunch()).toBeNull();
  });

  it("queues trimmed prompts and returns true", () => {
    expect(queueChatLaunch("  Study loops  ", "proj-1", "en", "vocab", "chat")).toBe(true);
    expect(takeQueuedChatLaunch()).toEqual({
      prompt: "Study loops",
      projectId: "proj-1",
      quizLanguage: "en",
      quizVariant: "vocab",
      quizMode: "chat",
    });
  });
});
