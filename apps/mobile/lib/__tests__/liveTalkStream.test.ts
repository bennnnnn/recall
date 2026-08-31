import type { Message } from "@/lib/api/types";
import {
  applyLiveTalkChatEvent,
  dropLiveTalkLocalTurn,
  parseLiveTalkSseChunk,
} from "@/lib/liveTalkEvents";

describe("liveTalkStream", () => {
  it("parses user, audio, and done SSE events", () => {
    const { events, rest } = parseLiveTalkSseChunk(
      'data: {"type":"user","text":"Hi"}\n\n' +
        'data: {"type":"audio","audio_base64":"AA==","content_type":"audio/wav"}\n\n' +
        'data: {"type":"done","remaining":28,"limit":30,"user_message":null,"assistant_message":null}\n\npartial',
    );
    expect(events.map((event) => event.type)).toEqual(["user", "audio", "done"]);
    expect(rest).toBe("partial");
  });

  it("upserts local bubbles then swaps in persisted messages", () => {
    const user: Message = {
      id: "u1",
      role: "user",
      content: "Hi",
      model: null,
      created_at: "2026-01-01T00:00:00Z",
    };
    const assistant: Message = {
      id: "a1",
      role: "assistant",
      content: "Hello",
      model: "live-talk-model",
      created_at: "2026-01-01T00:00:01Z",
    };
    let messages: Message[] = [];
    messages = applyLiveTalkChatEvent(messages, "t1", { type: "user", text: "Hi" });
    messages = applyLiveTalkChatEvent(messages, "t1", { type: "assistant", text: "Hel" });
    messages = applyLiveTalkChatEvent(messages, "t1", { type: "assistant", text: "Hello" });
    expect(messages).toHaveLength(2);
    expect(messages[1]?.content).toBe("Hello");
    messages = applyLiveTalkChatEvent(messages, "t1", {
      type: "done",
      remaining: 29,
      limit: 30,
      user_message: user,
      assistant_message: assistant,
    });
    expect(messages.map((row) => row.id)).toEqual(["u1", "a1"]);
  });

  it("keeps a voice placeholder until cancel drops the local turn", () => {
    let messages: Message[] = [];
    messages = applyLiveTalkChatEvent(messages, "t1", {
      type: "user",
      text: "Voice message",
    });
    expect(messages).toHaveLength(1);
    messages = dropLiveTalkLocalTurn(messages, "t1");
    expect(messages).toHaveLength(0);
  });
});
