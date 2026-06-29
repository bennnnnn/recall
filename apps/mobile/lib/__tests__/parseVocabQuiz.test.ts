import { cleanQuizWord, parseVocabQuiz, stripVocabQuizBlock } from "@/lib/parseVocabQuiz";

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

  it("strips stray asterisks from partial bold", () => {
    expect(cleanQuizWord("** Rain")).toBe("Rain");
    expect(cleanQuizWord("**Rain**")).toBe("Rain");
  });
});
