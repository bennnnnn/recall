import { deriveAssistantMessageContent } from "@/lib/markdown/assistantMessageContent";

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
    });

    expect(result.showSearchSources).toBe(false);
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
    // Icons mount at stream end; composer-gap pad (not a hidden slot) holds
    // the height so the layout-settle freeze cannot shift the prose.
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

  it("hides Sources on a where-am-I reply even when search hits leaked", () => {
    const result = deriveAssistantMessageContent({
      ...base,
      priorUserText: "Where am iI",
      content: "You're in **San Francisco, CA**.",
      liveSearchSources: [
        { title: "Los Baños", url: "https://example.com/lb" },
      ],
    });

    expect(result.searchSources).toHaveLength(1);
    expect(result.showSearchSources).toBe(false);
  });

  it("strips markdown A–D quizzes instead of exposing tap chips", () => {
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

    expect(result.interactiveQuiz).toBeNull();
    expect(result.markdownContent).not.toMatch(/^A\)/m);
    expect(result.markdownContent).not.toContain("Reply with A");
  });

  it("strips leftover vocab_quiz fences without exposing A–D chips", () => {
    const result = deriveAssistantMessageContent({
      ...base,
      content: [
        "Let's check this word.",
        "",
        "```vocab_quiz",
        JSON.stringify({
          word: "hola",
          question: "What does hola mean?",
          correct: "A",
          choices: [
            { letter: "A", text: "hello" },
            { letter: "B", text: "goodbye" },
            { letter: "C", text: "please" },
            { letter: "D", text: "thanks" },
          ],
        }),
        "```",
      ].join("\n"),
    });

    expect(result.interactiveQuiz).toBeNull();
    expect(result.markdownContent).not.toContain("vocab_quiz");
    expect(result.markdownContent).not.toContain("What does hola mean?");
  });

  it("strips vocab_card fences instead of rendering a study card in chat", () => {
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

    expect(result.showVocabCard).toBe(false);
    expect(result.vocabCard).toBeNull();
    expect(result.markdownContent).toContain("Write your own sentence");
    expect(result.markdownContent).not.toContain("vocab_card");
  });

  it("strips settings_proposal fences and exposes the card payload", () => {
    const result = deriveAssistantMessageContent({
      ...base,
      content: [
        "I can switch that for you: Appearance → Dark.",
        "```settings_proposal",
        '{"proposal_id":"abc","changes":[{"field":"appearance","value":"dark","label":"Dark"}]}',
        "```",
      ].join("\n"),
    });

    expect(result.showSettingsProposals).toBe(true);
    expect(result.settingsProposals[0]?.proposal_id).toBe("abc");
    expect(result.markdownContent).toBe("I can switch that for you: Appearance → Dark.");
  });

  it("exposes a learning_launch fence and hides the raw JSON", () => {
    const projectId = "11111111-1111-4111-8111-111111111111";
    const result = deriveAssistantMessageContent({
      ...base,
      content: [
        "You have 3/10 Spanish words today. Open the lesson when you're ready.",
        "```learning_launch",
        JSON.stringify({ project_id: projectId, action: "continue" }),
        "```",
      ].join("\n"),
    });

    expect(result.learningLaunch).toEqual({ projectId, action: "continue" });
    expect(result.markdownContent).toContain("3/10 Spanish");
    expect(result.markdownContent).not.toContain("learning_launch");
    expect(result.markdownContent).not.toContain(projectId);
  });
});
