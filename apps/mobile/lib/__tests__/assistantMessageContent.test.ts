import { deriveAssistantMessageContent } from "@/lib/assistantMessageContent";

describe("deriveAssistantMessageContent", () => {
  const base = {
    content: "Hello **world**",
    layoutFrozen: false,
    isUser: false,
    priorUserText: null,
    messageId: "msg-1",
    isGenerating: false,
  };

  it("returns empty markdown flags for user rows", () => {
    const result = deriveAssistantMessageContent({
      ...base,
      isUser: true,
    });

    expect(result.showActionSlot).toBe(false);
    expect(result.showSearchSources).toBe(false);
    expect(result.markdownContent).toBe("Hello **world**");
  });

  it("defers rich chrome while layout is frozen", () => {
    const result = deriveAssistantMessageContent({
      ...base,
      content: "Answer with ```search_sources\n[]\n```",
      layoutFrozen: true,
      contextSummarized: 1,
    });

    expect(result.showSearchSources).toBe(false);
    expect(result.showContextSummarized).toBe(false);
    expect(result.markdownStreamMode).toBe(true);
  });

  it("shows actions as soon as generation finishes (even mid layout settle)", () => {
    const ready = deriveAssistantMessageContent({
      ...base,
      isGenerating: false,
    });
    const streaming = deriveAssistantMessageContent({
      ...base,
      isGenerating: true,
    });
    const settling = deriveAssistantMessageContent({
      ...base,
      isGenerating: false,
      layoutFrozen: true,
    });

    expect(ready.actionsReady).toBe(true);
    expect(streaming.actionsReady).toBe(false);
    // The action slot is fixed-height, so icons can show while rich chrome
    // is still deferred — no layout shift.
    expect(settling.actionsReady).toBe(true);
  });

  it("builds markdown reset key from renderKey and content length", () => {
    const result = deriveAssistantMessageContent({
      ...base,
      renderKey: "stream-42",
      content: "Hi",
    });

    expect(result.markdownResetKey).toBe("stream-42:2");
  });

  it("hides action slot for local quiz feedback rows", () => {
    const result = deriveAssistantMessageContent({
      ...base,
      messageId: "local-quiz-1",
      content: "Correct!",
    });

    expect(result.isQuizFeedback).toBe(true);
    expect(result.showActionSlot).toBe(false);
  });

  it("parses assistant image markers and strips them from markdown", () => {
    const attachmentId = "11111111-1111-1111-1111-111111111111";
    const result = deriveAssistantMessageContent({
      ...base,
      content: `[Image: /attachments/${attachmentId}/file]`,
    });

    expect(result.showImages).toBe(true);
    expect(result.images).toHaveLength(1);
    expect(result.images[0]?.attachmentId).toBe(attachmentId);
    expect(result.markdownContent).toBe("");
    expect(result.hasMarkdown).toBe(false);
  });

  it("hides Sources under a live clock even when search hits are attached", () => {
    const result = deriveAssistantMessageContent({
      ...base,
      priorUserText: "What time is it in dc",
      content: "```clock\nAmerica/New_York\n```",
      liveSearchSources: [
        { title: "DC time", url: "https://example.com/dc" },
      ],
    });

    expect(result.showLiveClock).toBe(true);
    expect(result.searchSources).toHaveLength(1);
    expect(result.showSearchSources).toBe(false);
  });

  it("shows tap chips for markdown A–D even without a vocab_quiz fence", () => {
    const result = deriveAssistantMessageContent({
      ...base,
      content: [
        "**ephemeral**",
        "",
        "What does it mean?",
        "",
        "A) lasting forever",
        "B) very loud",
        "C) related to water",
        "D) lasting a short time",
        "",
        "Reply with A, B, C, or D.",
      ].join("\n"),
    });

    expect(result.interactiveQuiz).not.toBeNull();
    expect(result.interactiveQuiz?.word.toLowerCase()).toBe("ephemeral");
    expect(result.interactiveQuiz?.choices).toHaveLength(4);
    expect(result.markdownContent).not.toMatch(/^A\)/m);
    expect(result.markdownContent).toContain("ephemeral");
  });

  it("hides vocab_card example sentence when asking the user to write one", () => {
    const result = deriveAssistantMessageContent({
      ...base,
      content: [
        "Write your own sentence using **effervescent**.",
        "",
        "```vocab_card",
        JSON.stringify({
          word: "effervescent",
          definition: "bubbly and lively",
          example_sentence: "Her effervescent laughter filled the room.",
        }),
        "```",
      ].join("\n"),
    });

    expect(result.showVocabCard).toBe(true);
    expect(result.vocabCard?.word).toBe("effervescent");
    expect(result.vocabCard?.definition).toBe("bubbly and lively");
    expect(result.vocabCard?.exampleSentence).toBeUndefined();
  });
});
