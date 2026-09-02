import {
  cleanQuizWord,
  isVocabQuizAnswer,
  parseQuizAnswerLetter,
  parseVocabQuiz,
  hasVocabQuizFence,
  stripVocabQuizBlock,
  stripVocabQuizPrologue,
  stripVocabSessionMetadata,
} from "@/lib/parseVocabQuiz";

describe("parseVocabQuiz", () => {
  it("parses a formatted quiz block", () => {
    const content = [
      "Let's quiz!",
      "",
      "**Word:** slow",
      "What does it mean?",
      "A) Very fast",
      "B) Not fast",
      "C) Extremely loud",
      "D) A type of food",
    ].join("\n");

    const quiz = parseVocabQuiz(content);
    expect(quiz?.word).toBe("slow");
    expect(quiz?.choices).toHaveLength(4);
    expect(stripVocabQuizBlock(content)).toBe("Let's quiz!");
  });

  it("returns null when choices exist without a word header", () => {
    const content = [
      "Which sounds most fun?",
      "A) Very fast",
      "B) Not fast",
      "C) Extremely loud",
      "D) A type of food",
    ].join("\n");

    expect(parseVocabQuiz(content)).toBeNull();
  });

  it("strips markdown bold from the word", () => {
    const content = [
      "**Word:** **Rain**",
      "A) Water falling from clouds",
      "B) A red fruit",
      "C) Something you cook",
      "D) A fast runner",
    ].join("\n");

    expect(parseVocabQuiz(content)?.word).toBe("Rain");
  });

  it("parses correct letter from vocab_quiz fence", () => {
    const content = [
      "```vocab_quiz",
      JSON.stringify({
        word: "rain",
        question: "What does it mean?",
        correct: "A",
        choices: [
          { letter: "A", text: "Water from clouds" },
          { letter: "B", text: "A fruit" },
          { letter: "C", text: "A car" },
          { letter: "D", text: "A color" },
        ],
      }),
      "```",
    ].join("\n");

    const quiz = parseVocabQuiz(content);
    expect(quiz?.correct).toBe("A");
  });

  it("rejects vocab_quiz fence without correct letter", () => {
    const content = [
      "```vocab_quiz",
      JSON.stringify({
        word: "rain",
        choices: [
          { letter: "A", text: "Water from clouds" },
          { letter: "B", text: "A fruit" },
        ],
      }),
      "```",
    ].join("\n");

    expect(parseVocabQuiz(content)).toBeNull();
  });

  it("strips stray asterisks from partial bold", () => {
    expect(cleanQuizWord("** Rain")).toBe("Rain");
    expect(cleanQuizWord("**Rain**")).toBe("Rain");
  });

  it("detects single-letter quiz answers", () => {
    expect(isVocabQuizAnswer("A")).toBe(true);
    expect(isVocabQuizAnswer("b.")).toBe(true);
    expect(parseQuizAnswerLetter("C")).toBe("C");
    expect(parseQuizAnswerLetter("Is it a?")).toBe("A");
    expect(isVocabQuizAnswer("Is it a?")).toBe(true);
    expect(isVocabQuizAnswer("A bit more help")).toBe(false);
    expect(isVocabQuizAnswer("Hi")).toBe(false);
  });

  it("strips a partial vocab_quiz fence while streaming", () => {
    const content = [
      "Great — try this one:",
      "",
      "```vocab_quiz",
      '{"word":"slow","choices":[{"letter":"A","text":"Very fast"}',
    ].join("\n");

    expect(hasVocabQuizFence(content)).toBe(true);
    expect(stripVocabQuizBlock(content)).toBe("Great — try this one:");
    expect(stripVocabQuizBlock(content)).not.toContain("{");
  });

  it("strips a vocab_quiz JSON fence", () => {
    const content = [
      "Great — try this one:",
      "",
      "**Word:** slow",
      "A) Very fast",
      "B) Not fast",
      "C) Loud",
      "D) Food",
      "```vocab_quiz",
      JSON.stringify({
        word: "slow",
        question: "What does it mean?",
        choices: [
          { letter: "A", text: "Very fast" },
          { letter: "B", text: "Not fast" },
          { letter: "C", text: "Loud" },
          { letter: "D", text: "Food" },
        ],
      }),
      "```",
    ].join("\n");

    const quiz = parseVocabQuiz(content);
    expect(quiz?.word).toBe("slow");
    expect(quiz?.choices).toHaveLength(4);
    expect(stripVocabQuizBlock(content)).toBe("Great — try this one:");
    expect(stripVocabQuizBlock(content)).not.toContain("vocab_quiz");
  });

  it("strips duplicate trivia question text above a vocab_quiz fence", () => {
    const content = [
      "🎉 **Bingo!** Nice work.",
      "",
      "Next: **Pop Culture Throwdown**",
      "",
      '**Which American TV show famously had a "Central Perk" coffee shop?**',
      "",
      "```vocab_quiz",
      JSON.stringify({
        quiz_type: "trivia",
        word: "Pop Culture",
        question:
          'Which American TV show famously had a "Central Perk" coffee shop?',
        correct: "B",
        choices: [
          { letter: "A", text: "The Office" },
          { letter: "B", text: "Friends" },
          { letter: "C", text: "Seinfeld" },
          { letter: "D", text: "Parks and Rec" },
        ],
      }),
      "```",
    ].join("\n");

    const stripped = stripVocabQuizBlock(content);
    expect(stripped).toContain("Bingo!");
    expect(stripped).toContain("Pop Culture Throwdown");
    expect(stripped).not.toContain("Central Perk");
    expect(stripped).not.toContain("vocab_quiz");
  });

  it("strips trivia question with curly apostrophes and answer prompt line", () => {
    const ap = "\u2019";
    const content = [
      "Next: **Pop Culture Throwdown**",
      "",
      `**Which American TV show famously had a ${ap}Central Perk${ap} coffee shop?**`,
      "",
      "(Answer A, B, C, or D!) *Pivot! Pivot!*",
      "",
      "```vocab_quiz",
      JSON.stringify({
        quiz_type: "trivia",
        word: "Pop Culture",
        question:
          'Which American TV show famously had a "Central Perk" coffee shop?',
        correct: "B",
        choices: [
          { letter: "A", text: "The Office" },
          { letter: "B", text: "Friends" },
          { letter: "C", text: "Seinfeld" },
          { letter: "D", text: "Parks and Rec" },
        ],
      }),
      "```",
    ].join("\n");

    const stripped = stripVocabQuizBlock(content);
    expect(stripped).toContain("Pop Culture Throwdown");
    expect(stripped).not.toContain("Central Perk");
    expect(stripped).not.toContain("Answer A, B, C, or D");
    expect(stripped).not.toContain("Pivot");
  });

  it("strips session_complete json after daily vocab completion", () => {
    const content = [
      "🥳 **Congratulations, Dev!** You've mastered all 5 words today.",
      "",
      "```json",
      '{"session_complete":true,"words_learned":5,"streak":1}',
      "```",
    ].join("\n");

    expect(stripVocabSessionMetadata(content)).toBe(
      "🥳 **Congratulations, Dev!** You've mastered all 5 words today.",
    );
    expect(stripVocabQuizBlock(content)).not.toContain("session_complete");
  });

  it("stripVocabQuizPrologue removes duplicate definition before rendered A-D", () => {
    const content = [
      "Let's go! First word:",
      "To rest on a chair or the ground.",
      '"Please sit on the chair."',
      'What does "sit" mean?',
      "",
      "```vocab_quiz",
      JSON.stringify({
        word: "sit",
        question: "What does it mean?",
        correct: "B",
        choices: [
          { letter: "A", text: "To run quickly" },
          { letter: "B", text: "To rest on a chair or the ground" },
          { letter: "C", text: "To jump up and down" },
          { letter: "D", text: "To sing a song" },
        ],
      }),
      "```",
    ].join("\n");

    const quiz = parseVocabQuiz(content);
    expect(quiz).not.toBeNull();
    const intro = stripVocabQuizBlock(content);
    const trimmed = stripVocabQuizPrologue(intro, quiz!);
    expect(trimmed).toBe("Let's go! First word:");
    expect(trimmed).not.toContain("What does");
    expect(trimmed).not.toContain("Please sit");
    expect(trimmed).not.toContain("To rest on a chair");
  });
});
