import {
  buildChapterLessonPrompt,
  buildProjectChatTutorPrompt,
  buildProjectPracticePrompt,
} from "@/lib/projects/projectChat";
import type { ProjectDetail } from "@/lib/api";

function languageProject(overrides: Partial<ProjectDetail> = {}): ProjectDetail {
  return {
    id: "lang-1",
    kind: "language",
    title: "English",
    description: "daily words",
    level: "level1",
    target_language: "en",
    daily_goal: 5,
    stats: {
      total: 10,
      mastered_count: 8,
      new_count: 0,
      learning_count: 2,
      due_for_review: 0,
      added_this_week: 5,
      mastered_today: 2,
      pending_today: 0,
    },
    lists: [],
    ...overrides,
  } as unknown as ProjectDetail;
}

describe("buildProjectPracticePrompt", () => {
  it("references the project title and kind", () => {
    const prompt = buildProjectPracticePrompt(languageProject());
    expect(prompt).toContain("English");
    expect(prompt).toContain("language");
    expect(prompt).toContain("practice problem");
  });

  it("includes the goal when a description is set", () => {
    const prompt = buildProjectPracticePrompt(languageProject());
    expect(prompt).toContain("daily words");
  });

  it("omits the goal clause when there is no description", () => {
    const prompt = buildProjectPracticePrompt(languageProject({ description: "" }));
    expect(prompt).not.toContain("Goal:");
  });

  it("asks Recall to check the answer and suggest next steps", () => {
    const prompt = buildProjectPracticePrompt(languageProject());
    expect(prompt).toContain("check my answer");
    expect(prompt).toContain("what to try next");
  });
});

describe("buildChapterLessonPrompt", () => {
  it("scopes the lesson to the named chapter", () => {
    const prompt = buildChapterLessonPrompt(
      languageProject({ title: "Spanish", target_language: "es" }),
      "Greetings",
    );
    expect(prompt).toContain('"Greetings" chapter');
    expect(prompt).toContain('Add any new words to "Greetings"');
    expect(prompt).toContain("one word at a time");
    expect(prompt).toContain("ONLY one ```vocab_quiz or ```vocab_card");
  });
});

describe("buildProjectChatTutorPrompt", () => {
  it("language chat tutor uses vocab cards", () => {
    const prompt = buildProjectChatTutorPrompt(languageProject());
    expect(prompt).toContain("vocab_card format");
    expect(prompt).toContain("no example sentence");
  });
});
