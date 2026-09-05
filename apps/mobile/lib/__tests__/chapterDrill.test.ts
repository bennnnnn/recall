import type { ProjectItem } from "@/lib/api";
import {
  blankTargetWord,
  buildChapterDrills,
  isLastStepForWord,
  lessonWordProgress,
  pickTexts,
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
  it("never blanks a lemma inside another word", () => {
    expect(blankTargetWord("The hotel is quiet.", "he")).toBeNull();
  });

  it("uses a meaning assessment when examples contain only an inflected form", () => {
    const wake = {
      ...item("1", "despertarse", "Dejar de dormir."),
      example_sentence: "Me despierto temprano.",
    };
    const sleep = item("2", "dormir", "Descansar durante la noche.");
    const steps = buildChapterDrills([wake], [wake, sleep], labels);
    expect(steps.map((step) => step.kind)).toEqual(["teach", "meaning"]);
    expect(steps[1]).toMatchObject({ question: expect.stringContaining("despertarse") });
    expect(steps[1]).toMatchObject({ question: expect.not.stringContaining("_____") });
  });

  it("blanks the target word in the example sentence", () => {
    expect(blankTargetWord("Hello, how are you?", "hello")).toBe("_____, how are you?");
    expect(blankTargetWord("See you later.", "see you later")).toBe("_____.");
    expect(blankTargetWord("No match here.", "hola")).toBeNull();
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
    expect(meaning.contextSentence).toBe("Say hola.");
    expect(meaning.question).not.toMatch(/what does/i);
  });

  it("samples distractors from the whole pool, not the first three", () => {
    const pool = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel"];
    const seen = new Set<string>();
    for (const seed of ["a", "b", "c", "d", "e", "f", "g", "h"]) {
      for (const text of pickTexts(pool, "alpha", seed, [])) {
        if (text !== "alpha") seen.add(text);
      }
    }
    expect(seen.size).toBeGreaterThan(3);
  });

  it("counts words in the chapter, not teach/quiz steps", () => {
    const words = [item("1", "hi", "hello"), item("2", "bye", "goodbye")];
    const drills = buildChapterDrills(words, words, labels);
    expect(drills).toHaveLength(6);
    expect(lessonWordProgress(drills, 0)).toEqual({ current: 1, total: 2, fill: 1 / 6 });
    expect(lessonWordProgress(drills, 2).current).toBe(1);
    expect(lessonWordProgress(drills, 3)).toMatchObject({ current: 2, total: 2 });
    expect(lessonWordProgress(drills, 6)).toEqual({ current: 2, total: 2, fill: 1 });
    expect(isLastStepForWord(drills, 2)).toBe(true);
    expect(isLastStepForWord(drills, 0)).toBe(false);
  });

  it("does not award a teaching-only completion when no assessment is possible", () => {
    const only = item("1", "hola", "hello");
    const drills = buildChapterDrills([only], [only], labels);
    expect(drills).toEqual([]);
  });
});

it("does not include punctuation/spacing variants of the answer as different meanings", () => {
  expect(
    pickTexts(["A greeting", "a   greeting.", "Farewell"], "A greeting.", "one", []),
  ).toHaveLength(2);
});
it("does not use another word with the same definition as a cloze distractor", () => {
  const hello = item("1", "hello", "A greeting.");
  const hi = item("2", "hi", "a greeting");
  const bye = item("3", "bye", "Farewell.");
  const quiz = buildChapterDrills([hello], [hello, hi, bye], labels).find(
    (step) => step.kind === "use",
  );
  if (quiz?.kind !== "use") throw new Error("Expected cloze");
  expect(quiz.quiz.choices.map((choice) => choice.text)).not.toContain("hi");
});
