import {
  buildProjectChatTutorPrompt,
  buildProjectPracticePrompt,
} from "@/lib/projectChat";
import type { ProjectDetail } from "@/lib/api";

function mathProject(overrides: Partial<ProjectDetail> = {}): ProjectDetail {
  return {
    id: "math-1",
    kind: "math",
    title: "Algebra basics",
    description: "Linear equations for exams",
    level: "beginner",
    target_language: "en",
    stats: {
      total: 0,
      mastered_count: 0,
      new_count: 0,
      learning_count: 0,
      due_for_review: 0,
      added_this_week: 0,
    },
    decks: [],
    pos_groups: [],
    by_part_of_speech: [],
    lists: [],
    ...overrides,
  } as unknown as ProjectDetail;
}

describe("buildProjectPracticePrompt", () => {
  it("references the project title and kind", () => {
    const prompt = buildProjectPracticePrompt(mathProject());
    expect(prompt).toContain("Algebra basics");
    expect(prompt).toContain("math");
    expect(prompt).toContain("practice problem");
  });

  it("includes the goal when a description is set", () => {
    const prompt = buildProjectPracticePrompt(mathProject());
    expect(prompt).toContain("Linear equations for exams");
  });

  it("omits the goal clause when there is no description", () => {
    const prompt = buildProjectPracticePrompt(mathProject({ description: "" }));
    expect(prompt).not.toContain("Goal:");
  });

  it("asks Recall to check the answer and suggest next steps", () => {
    const prompt = buildProjectPracticePrompt(mathProject());
    expect(prompt).toContain("check my answer");
    expect(prompt).toContain("what to try next");
  });
});

function triviaProject(overrides: Partial<ProjectDetail> = {}): ProjectDetail {
  return {
    id: "trivia-1",
    kind: "trivia",
    title: "General knowledge",
    description: "history,science",
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
      mastered_today: 8,
      pending_today: 0,
    },
    decks: [],
    pos_groups: [],
    by_part_of_speech: [],
    lists: [],
    ...overrides,
  } as unknown as ProjectDetail;
}

describe("buildProjectChatTutorPrompt", () => {
  it("trivia chat tutor avoids vocabulary teaching", () => {
    const prompt = buildProjectChatTutorPrompt(triviaProject());
    expect(prompt).toContain("general knowledge");
    expect(prompt).toContain("Do NOT teach English vocabulary");
    expect(prompt).not.toContain("vocab_card format");
    expect(prompt).toContain("today's quiz goal is complete");
  });

  it("language chat tutor uses vocab cards", () => {
    const prompt = buildProjectChatTutorPrompt({
      ...triviaProject(),
      kind: "language",
      title: "English",
      stats: { ...triviaProject().stats, mastered_today: 2 },
    } as ProjectDetail);
    expect(prompt).toContain("vocab_card format");
    expect(prompt).not.toContain("Do NOT teach English vocabulary");
  });
});
