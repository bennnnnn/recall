import {
  cleanQuizWord,
  inferQuizAnswersFromMessages,
  isVocabQuizAnswer,
  parseQuizAnswerLetter,
  parseVocabQuiz,
  stripVocabQuizBlock,
  isCompleteVocabQuiz,
} from "@/lib/parseVocabQuiz";

describe("parseVocabQuiz", () => {
  it("parses a formatted quiz block", () => {
    const content = [
      "Let's quiz!",
      "",
      "**Word:** slow [adjective]",
      "What does it mean?",
      "A) Very fast",
      "B) Not fast",
      "C) Extremely loud",
      "D) A type of food",
    ].join("\n");

    const quiz = parseVocabQuiz(content);
    expect(quiz?.word).toBe("slow");
    expect(quiz?.partOfSpeech).toBe("adjective");
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
      "**Word:** **Rain** [noun]",
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
        part_of_speech: "noun",
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

  it("isCompleteVocabQuiz requires four choices", () => {
    expect(
      isCompleteVocabQuiz({
        word: "cat",
        choices: [
          { letter: "A", text: "a" },
          { letter: "B", text: "b" },
          { letter: "C", text: "c" },
          { letter: "D", text: "d" },
        ],
      }),
    ).toBe(true);
    expect(
      isCompleteVocabQuiz({
        word: "cat",
        choices: [
          { letter: "A", text: "a" },
          { letter: "B", text: "b" },
        ],
      }),
    ).toBe(false);
  });

  it("strips stray asterisks from partial bold", () => {
    expect(cleanQuizWord("** Rain")).toBe("Rain");
    expect(cleanQuizWord("**Rain**")).toBe("Rain");
  });

  it("detects single-letter quiz answers", () => {
    expect(isVocabQuizAnswer("A")).toBe(true);
    expect(isVocabQuizAnswer("b.")).toBe(true);
    expect(parseQuizAnswerLetter("C")).toBe("C");
    expect(isVocabQuizAnswer("Hi")).toBe(false);
  });

  it("infers quiz answers from message pairs", () => {
    const quizBody = [
      "**Word:** apple [noun]",
      "What does it mean?",
      "A) a red fruit",
      "B) a vehicle",
      "C) a feeling",
      "D) a color",
    ].join("\n");
    const answers = inferQuizAnswersFromMessages([
      { id: "q1", role: "assistant", content: quizBody },
      { id: "u1", role: "user", content: "A" },
      { id: "q2", role: "assistant", content: quizBody },
      { id: "u2", role: "user", content: "B" },
    ]);
    expect(answers.q1).toBe("A");
    expect(answers.q2).toBe("B");
  });

  it("parses a vocab_quiz JSON fence", () => {
    const content = [
      "Great — try this one:",
      "",
      "**Word:** slow [adjective]",
      "A) Very fast",
      "B) Not fast",
      "C) Loud",
      "D) Food",
      "```vocab_quiz",
      JSON.stringify({
        word: "slow",
        part_of_speech: "adjective",
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
    expect(stripVocabQuizBlock(content)).not.toContain("vocab_quiz");
  });
});
