import {
  buildProjectAskPrompt,
  buildProjectBonusWordsPrompt,
  isDailyGoalMet,
  remainingDailyGoal,
} from "@/lib/projectChat";
import type { ProjectDetail } from "@/lib/api";

function languageProject(overrides: Partial<ProjectDetail> = {}): ProjectDetail {
  return {
    id: "lang-1",
    kind: "language",
    title: "English · Beginner",
    description: null,
    level: "level1",
    target_language: "en",
    daily_goal: 5,
    stats: {
      total: 8,
      mastered_count: 6,
      new_count: 1,
      learning_count: 1,
      due_for_review: 0,
      added_this_week: 5,
      mastered_today: 3,
      pending_today: 2,
    },
    decks: [],
    pos_groups: [],
    by_part_of_speech: [],
    lists: [],
    ...overrides,
  } as unknown as ProjectDetail;
}

describe("projectChat daily goal helpers", () => {
  it("detects when daily goal is met", () => {
    expect(isDailyGoalMet(languageProject({ stats: { ...languageProject().stats, mastered_today: 5 } }))).toBe(
      true,
    );
    expect(isDailyGoalMet(languageProject())).toBe(false);
  });

  it("computes remaining daily goal", () => {
    expect(remainingDailyGoal(languageProject())).toBe(2);
    expect(
      remainingDailyGoal(languageProject({ stats: { ...languageProject().stats, mastered_today: 6 } })),
    ).toBe(0);
  });

  it("in-progress prompt asks to stay within today's goal", () => {
    const prompt = buildProjectAskPrompt(languageProject());
    expect(prompt).toContain("3/5 mastered");
    expect(prompt).toContain("2 left for today's goal");
    expect(prompt).not.toContain("generate today's batch");
  });

  it("completed prompt tells Recall not to add words", () => {
    const prompt = buildProjectAskPrompt(
      languageProject({ stats: { ...languageProject().stats, mastered_today: 5 } }),
    );
    expect(prompt).toContain("finished my daily goal");
    expect(prompt).toContain("Do NOT add or sync new words");
  });

  it("bonus prompt requires explicit opt-in", () => {
    const prompt = buildProjectBonusWordsPrompt(
      languageProject({ stats: { ...languageProject().stats, mastered_today: 5 } }),
    );
    expect(prompt).toContain("BONUS batch");
    expect(prompt).toContain("Do not start until I confirm");
  });
});
