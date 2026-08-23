import {
  findActiveQuizMessageId,
  findLastAssistantId,
  findLastLocalUserMessageId,
  isChatStreamActive,
  isLocalPendingMessageId,
  priorAssistantIsQuizFor,
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

  it("findActiveQuizMessageId keeps the prior quiz after a hint-only wrong reply", () => {
    const quiz = [
      "**History**",
      "",
      "Which war?",
      "",
      "```vocab_quiz",
      JSON.stringify({
        quiz_type: "trivia",
        word: "History",
        question: "Which war?",
        correct: "A",
        choices: [
          { letter: "A", text: "Thirty Years' War" },
          { letter: "B", text: "English Civil War" },
          { letter: "C", text: "Franco-Dutch War" },
          { letter: "D", text: "War of the Spanish Succession" },
        ],
      }),
      "```",
    ].join("\n");
    const messages = [
      { id: "q1", role: "assistant", content: quiz },
      { id: "u1", role: "user", content: "D" },
      { id: "h1", role: "assistant", content: "You were wrong — hint: began in 1618." },
    ] as Message[];

    expect(findLastAssistantId(messages)).toBe("h1");
    expect(findActiveQuizMessageId(messages)).toBe("q1");
  });

  it("findActiveQuizMessageId skips re-emitted fence in hint-only reply (LANG-STATE-001)", () => {
    const quiz = [
      "```vocab_quiz",
      JSON.stringify({
        quiz_type: "vocab",
        word: "serendipity",
        question: "What word means a happy coincidence?",
        correct: "A",
        choices: [
          { letter: "A", text: "serendipity" },
          { letter: "B", text: "ephemeral" },
          { letter: "C", text: "ubiquitous" },
          { letter: "D", text: "candid" },
        ],
      }),
      "```",
    ].join("\n");
    // Model re-emits the same fence despite "do NOT redisplay" instruction
    const messages = [
      { id: "q1", role: "assistant", content: quiz },
      { id: "u1", role: "user", content: "B" },
      { id: "h1", role: "assistant", content: quiz }, // re-emitted fence
    ] as Message[];

    expect(findActiveQuizMessageId(messages)).toBe("q1");
  });

  it("findActiveQuizMessageId accepts markdown A–D without a fence", () => {
    const markdownQuiz = [
      "**ephemeral**",
      "",
      "What does it mean?",
      "",
      "A) lasting forever",
      "B) very loud",
      "C) related to water",
      "D) lasting a short time",
    ].join("\n");
    const messages = [{ id: "m1", role: "assistant", content: markdownQuiz }] as Message[];

    expect(findActiveQuizMessageId(messages)).toBe("m1");
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

  describe("priorAssistantIsQuizFor", () => {
    const quiz = [
      "```vocab_quiz",
      JSON.stringify({
        quiz_type: "vocab",
        word: "serendipity",
        question: "What word means a happy coincidence?",
        correct: "A",
        choices: [
          { letter: "A", text: "serendipity" },
          { letter: "B", text: "ephemeral" },
          { letter: "C", text: "ubiquitous" },
          { letter: "D", text: "candid" },
        ],
      }),
      "```",
    ].join("\n");

    it("is false for a letter after a normal assistant reply", () => {
      const messages = [
        { id: "u1", role: "user", content: "Hi" },
        { id: "a1", role: "assistant", content: "Hello!" },
        { id: "u2", role: "user", content: "c" },
      ] as Message[];
      expect(priorAssistantIsQuizFor(messages, 2)).toBe(false);
    });

    it("is true for a letter immediately after a quiz fence", () => {
      const messages = [
        { id: "q1", role: "assistant", content: quiz },
        { id: "u1", role: "user", content: "C" },
      ] as Message[];
      expect(priorAssistantIsQuizFor(messages, 1)).toBe(true);
    });

    it("is true for a letter after a wrong-answer hint", () => {
      const messages = [
        { id: "q1", role: "assistant", content: quiz },
        { id: "u1", role: "user", content: "D" },
        { id: "h1", role: "assistant", content: "Not quite — think coincidence." },
        { id: "u2", role: "user", content: "A" },
      ] as Message[];
      expect(priorAssistantIsQuizFor(messages, 3)).toBe(true);
    });

    it("is false for a later letter once the chat has moved on", () => {
      const messages = [
        { id: "q1", role: "assistant", content: quiz },
        { id: "u1", role: "user", content: "A" },
        { id: "a1", role: "assistant", content: "Nice — that's it." },
        { id: "u2", role: "user", content: "thanks" },
        { id: "a2", role: "assistant", content: "Anytime." },
        { id: "u3", role: "user", content: "c" },
      ] as Message[];
      expect(priorAssistantIsQuizFor(messages, 5)).toBe(false);
    });
  });
});
