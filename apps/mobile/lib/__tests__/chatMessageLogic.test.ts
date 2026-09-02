import {
  findLastAssistantId,
  findLastLocalUserMessageId,
  isChatStreamActive,
  isLocalPendingMessageId,
  priorUserTextFor,
  streamVisualActiveForRow,
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

  describe("streamVisualActiveForRow", () => {
    it("returns the real value for a user row while a turn is active", () => {
      expect(streamVisualActiveForRow("user", "u1", "a2", true, false)).toBe(true);
      expect(streamVisualActiveForRow("user", "u1", "a2", false, false)).toBe(false);
    });

    it("returns the real value for the row matching lastAssistantId", () => {
      expect(streamVisualActiveForRow("assistant", "a2", "a2", true, false)).toBe(true);
      expect(streamVisualActiveForRow("assistant", "a2", "a2", false, true)).toBe(true);
    });

    it("returns a stable false for other assistant rows regardless of stream state", () => {
      expect(streamVisualActiveForRow("assistant", "a1", "a2", true, false)).toBe(false);
      expect(streamVisualActiveForRow("assistant", "a1", "a2", false, true)).toBe(false);
    });

    it("returns false for a user row when no turn is active", () => {
      expect(streamVisualActiveForRow("user", "u1", null, false, false)).toBe(false);
    });
  });

  describe("priorUserTextFor", () => {
    const messages = [
      { id: "1", role: "user", content: "what's the weather" },
      { id: "2", role: "assistant", content: "sunny" },
      { id: "3", role: "assistant", content: "anything else?" },
    ] as Message[];

    it("returns the preceding user message's content for an assistant reply", () => {
      expect(priorUserTextFor(messages, 1)).toBe("what's the weather");
    });

    it("returns null when the preceding item isn't a user message", () => {
      expect(priorUserTextFor(messages, 2)).toBeNull();
    });

    it("returns null for a user message", () => {
      expect(priorUserTextFor(messages, 0)).toBeNull();
    });

    it("returns null at index 0 even if it were an assistant message", () => {
      const leading = [{ id: "1", role: "assistant", content: "hi" }] as Message[];
      expect(priorUserTextFor(leading, 0)).toBeNull();
    });

    it("returns null for an out-of-range index", () => {
      expect(priorUserTextFor(messages, 99)).toBeNull();
    });
  });
});
