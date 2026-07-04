import { mergeDoneIntoMessages, appendToken, buildDoneMergeInput } from "@/lib/chatSocketReduce";
import type { Message } from "@/lib/api";

describe("chatSocketReduce", () => {
  it("appendToken concatenates stream chunks", () => {
    expect(appendToken("Hi", " there")).toBe("Hi there");
    expect(appendToken("Hi", undefined)).toBe("Hi");
  });

  it("mergeDoneIntoMessages replaces streaming placeholder", () => {
    const prev: Message[] = [
      { id: "u1", role: "user", content: "Hello", model: null, created_at: "t" },
      {
        id: "streaming",
        renderKey: "stream-1",
        role: "assistant",
        content: "",
        model: null,
        created_at: "t",
      },
    ];
    const next = mergeDoneIntoMessages(prev, {
      finalId: "msg-1",
      messageId: "msg-1",
      draftContent: "Hi back",
    });
    expect(next).toHaveLength(2);
    expect(next[1].id).toBe("msg-1");
    expect(next[1].renderKey).toBe("stream-1");
    expect(next[1].content).toBe("Hi back");
  });

  it("mergeDoneIntoMessages drops empty streaming bubble without message_id", () => {
    const prev: Message[] = [
      { id: "streaming", role: "assistant", content: "", model: null, created_at: "t" },
    ];
    const next = mergeDoneIntoMessages(prev, {
      finalId: "x",
      draftContent: "   ",
    });
    expect(next).toHaveLength(0);
  });

  it("mergeDoneIntoMessages prefers final_content on streaming placeholder", () => {
    const prev: Message[] = [
      { id: "streaming", role: "assistant", content: "Intro\n```places", model: null, created_at: "t" },
    ];
    const next = mergeDoneIntoMessages(prev, {
      finalId: "msg-1",
      messageId: "msg-1",
      draftContent: "Intro\n```places",
      finalContent: "Intro\n\n```places\n[{\"name\":\"A\"}]\n```",
    });
    expect(next[0].content).toContain("```places");
  });

  it("mergeDoneIntoMessages prefers final_content on stop for last assistant", () => {
    const prev: Message[] = [
      { id: "u1", role: "user", content: "Q", model: null, created_at: "t" },
      {
        id: "streamed-1",
        role: "assistant",
        content: "Partial",
        model: null,
        created_at: "t",
      },
    ];
    const next = mergeDoneIntoMessages(prev, {
      finalId: "msg-final",
      messageId: "msg-final",
      draftContent: "Partial",
      finalContent: "Partial plus more from server",
    });
    expect(next[1].content).toBe("Partial plus more from server");
  });

  it("buildDoneMergeInput parses metadata fields", () => {
    const input = buildDoneMergeInput(
      {
        type: "done",
        message_id: "abc",
        recalled: "2",
        memory_hints: '["goal"]',
        final_content: "Full text",
      },
      { content: "Full text" },
      123,
    );
    expect(input.finalId).toBe("abc");
    expect(input.recalled).toBe(2);
    expect(input.memory_hints).toEqual(["goal"]);
    expect(input.finalContent).toBe("Full text");
  });

  it("buildDoneMergeInput captures resolved_model", () => {
    const input = buildDoneMergeInput(
      {
        type: "done",
        message_id: "abc",
        resolved_model: "smart-chat",
      },
      { content: "Hi" },
    );
    expect(input.model).toBe("smart-chat");
  });

  it("mergeDoneIntoMessages stores resolved model on assistant message", () => {
    const prev: Message[] = [
      { id: "u1", role: "user", content: "Hi", model: null, created_at: "" },
      { id: "streaming", role: "assistant", content: "Hello", model: null, created_at: "" },
    ];
    const next = mergeDoneIntoMessages(prev, {
      finalId: "a1",
      messageId: "a1",
      draftContent: "Hello",
      model: "free-chat",
    });
    expect(next[1].model).toBe("free-chat");
  });
});
