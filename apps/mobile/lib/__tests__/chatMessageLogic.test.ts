import {
  findLastAssistantId,
  findLastLocalUserMessageId,
  isChatStreamActive,
  isLocalPendingMessageId,
} from "@/lib/chatMessageLogic";
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

  it("findLastLocalUserMessageId returns the latest optimistic user message", () => {
    const messages = [
      { id: "local-1", role: "user", content: "first" },
      { id: "2", role: "assistant", content: "hello" },
      { id: "local-2", role: "user", content: "second" },
    ] as Message[];

    expect(findLastLocalUserMessageId(messages)).toBe("local-2");
    expect(isLocalPendingMessageId("local-edit-3")).toBe(true);
    expect(isLocalPendingMessageId("abc")).toBe(false);
  });

  it("isChatStreamActive stays true during post-stream finalization", () => {
    expect(isChatStreamActive(true, false)).toBe(true);
    expect(isChatStreamActive(false, true)).toBe(true);
    expect(isChatStreamActive(false, false)).toBe(false);
  });
});
