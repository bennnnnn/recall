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

  it("shows actions when generation finished and layout settled", () => {
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
    expect(settling.actionsReady).toBe(false);
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
});
