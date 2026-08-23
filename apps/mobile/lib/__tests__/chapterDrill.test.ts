import type { ProjectItem } from "@/lib/api";
import {
  blankTargetWord,
  buildChapterDrills,
  lessonWordProgress,
} from "@/lib/projects/chapterDrill";

function item(id: string, content: string, definition: string): ProjectItem {
  return {
    id,
    list_title: "Greetings",
    content,
    note: null,
    definition,
    example_sentence: `Say ${content}.`,
    status: "new",
    mastered: false,
    mastered_at: null,
    last_reviewed_at: null,
    review_count: 0,
    pronunciation_url: null,
    created_at: "2026-01-01T00:00:00Z",
  };
}

const labels = {
  useQuestion: (sentence: string) => `Which word completes this sentence?\n${sentence}`,
  meaningQuestion: (sentence: string) => `In this sentence, it means:\n${sentence}`,
};

describe("buildChapterDrills", () => {
  it("blanks the target word in the example sentence", () => {
    expect(blankTargetWord("Hello, how are you?", "hello")).toBe("_____, how are you?");
    expect(blankTargetWord("See you later.", "see you later")).toBe("_____.");
    expect(blankTargetWord("No match here.", "hola")).toBe("No match here. (_____)");
  });

  it("teaches a word, then quizzes a gapped sentence, then meaning in context", () => {
    const hola = item("1", "hola", "hello");
    const adios = item("2", "adiós", "goodbye");
    const gracias = item("3", "gracias", "thank you");
    const please = item("4", "por favor", "please");
    const drills = buildChapterDrills([hola], [hola, adios, gracias, please], labels);

    expect(drills.map((step) => step.kind)).toEqual(["teach", "use", "meaning"]);
    expect(drills[0]).toMatchObject({
      kind: "teach",
      card: { word: "hola", definition: "hello" },
    });

    const use = drills[1];
    const meaning = drills[2];
    if (use?.kind !== "use" || meaning?.kind !== "meaning") {
      throw new Error("expected quiz steps");
    }
    expect(use.question).toContain("_____");
    expect(use.question).not.toMatch(/what does/i);
    expect(use.quiz.choices).toHaveLength(4);
    expect(use.quiz.choices.map((choice) => choice.text)).toContain("hola");
    expect(use.quiz.correct).toBe(
      use.quiz.choices.find((choice) => choice.text === "hola")?.letter,
    );
    expect(meaning.quiz.choices.map((choice) => choice.text)).toContain("hello");
    expect(meaning.question).toContain("_____");
    expect(meaning.question).not.toMatch(/what does/i);
  });

  it("counts words in the chapter, not teach/quiz steps", () => {
    const words = [item("1", "hi", "hello"), item("2", "bye", "goodbye")];
    const drills = buildChapterDrills(words, words, labels);
    expect(drills).toHaveLength(6);
    expect(lessonWordProgress(drills, 0)).toEqual({ current: 1, total: 2, fill: 1 / 6 });
    expect(lessonWordProgress(drills, 2).current).toBe(1);
    expect(lessonWordProgress(drills, 3)).toMatchObject({ current: 2, total: 2 });
    expect(lessonWordProgress(drills, 6)).toEqual({ current: 2, total: 2, fill: 1 });
  });
});
