import { findLastAssistantId } from "@/lib/chatMessageLogic";
import type { Message } from "@/lib/api";

describe("chatMessageLogic", () => {
  it("findLastAssistantId returns the latest assistant message", () => {
    const messages = [
      { id: "1", role: "user", content: "hi" },
      { id: "2", role: "assistant", content: "hello" },
      { id: "3", role: "user", content: "again" },
      { id: "4", role: "assistant", content: "sure" },
    ] as Message[];

    expect(findLastAssistantId(messages)).toBe("4");
    expect(findLastAssistantId([])).toBeNull();
    expect(findLastAssistantId([{ id: "1", role: "user", content: "x" } as Message])).toBeNull();
  });
});
