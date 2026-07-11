import {
  buildProjectAskPrompt,
  buildProjectAskPromptFromProject,
  buildProjectBonusQuestionsPrompt,
  buildProjectBonusWordsPrompt,
  isDailyGoalMet,
  remainingDailyGoal,
} from "@/lib/projectChat";
import type { ProjectDetail } from "@/lib/api";

const t = (key: string) => key;

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
    lists: [],
    ...overrides,
  } as unknown as ProjectDetail;
}

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
      mastered_today: 3,
      pending_today: 0,
    },
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

  it("in-progress words prompt includes level and today progress", () => {
    const prompt = buildProjectAskPrompt(languageProject(), { screenTitle: "Words" });
    expect(prompt).toContain("Continue my Words session.");
    expect(prompt).toContain("Level: Beginner.");
    expect(prompt).toContain("Today: 3/5 done (3 mastered, 0 failed)");
    expect(prompt).toMatch(/teach→use|learning format|use→define/);
    expect(prompt).not.toContain("Goal:");
    expect(prompt).not.toContain("you pick the format");
    expect(prompt).not.toContain("ask the next multiple-choice question");
  });

  it("in-progress trivia prompt uses topics and difficulty, not raw goal", () => {
    const prompt = buildProjectAskPrompt(triviaProject(), {
      screenTitle: "General Knowledge",
      topicLabels: "History, Science",
      difficultyLabel: "Easy",
    });
    expect(prompt).toContain("Continue my General Knowledge session.");
    expect(prompt).toContain("Topics: History, Science.");
    expect(prompt).toContain("Difficulty: Easy.");
    expect(prompt).toContain("Today: 3/5 done (3 correct, 0 failed)");
    expect(prompt).toContain("multiple-choice");
    expect(prompt).not.toContain("Goal: history");
  });

  it("buildProjectAskPromptFromProject localizes screen title and topics", () => {
    const prompt = buildProjectAskPromptFromProject(triviaProject(), t);
    expect(prompt).toContain("projects.trivia.title");
    expect(prompt).toContain("projects.trivia.topic.history");
    expect(prompt).toContain("projects.trivia.difficulty.easy");
    expect(prompt).toContain("Today: 3/5 done (3 correct, 0 failed)");
  });

  it("completed prompt tells Recall not to add words", () => {
    const prompt = buildProjectAskPrompt(
      languageProject({ stats: { ...languageProject().stats, mastered_today: 5 } }),
      { screenTitle: "Words" },
    );
    expect(prompt).toContain("finished my daily goal");
    expect(prompt).toContain("Do NOT add or sync new words");
  });

  it("bonus trivia prompt starts interactive quiz format", () => {
    const prompt = buildProjectBonusQuestionsPrompt(
      triviaProject({ stats: { ...triviaProject().stats, mastered_today: 5 } }),
    );
    expect(prompt).toContain("BONUS trivia");
    expect(prompt).toContain("vocab_quiz");
    expect(prompt).toContain("quiz_type");
    expect(prompt).toContain("Start the first bonus question now");
  });

  it("bonus words prompt requires explicit opt-in", () => {
    const prompt = buildProjectBonusWordsPrompt(
      languageProject({ stats: { ...languageProject().stats, mastered_today: 5 } }),
    );
    expect(prompt).toContain("BONUS batch");
    expect(prompt).toContain("Do not start until I confirm");
  });
});
