import { queueChatLaunch, queueDailyQuizLaunch, takeQueuedChatLaunch } from "@/lib/chatLaunch";

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

  it("queues trimmed prompts and defaults to chat mode", () => {
    expect(queueChatLaunch("  Study loops  ", "proj-1", "en", "vocab", "chat")).toBe(true);
    expect(takeQueuedChatLaunch()).toEqual({
      prompt: "Study loops",
      projectId: "proj-1",
      quizLanguage: "en",
      quizVariant: "vocab",
      quizMode: "chat",
    });
  });

  it("queueDailyQuizLaunch opens chat mode with a starter prompt", () => {
    expect(queueDailyQuizLaunch("proj-2", "trivia")).toBe(true);
    expect(takeQueuedChatLaunch()).toEqual({
      prompt: expect.stringContaining("general-knowledge"),
      projectId: "proj-2",
      quizVariant: "trivia",
      quizMode: "chat",
    });
  });
});
