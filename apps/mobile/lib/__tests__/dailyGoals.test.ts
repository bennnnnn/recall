import {
  dailyGoalPickerOptions,
  formatDailyGoalLabel,
  resolveDailyGoal,
  VOCAB_DAILY_GOALS,
} from "@/lib/dailyGoals";

describe("dailyGoals", () => {
  const t = (key: string, options?: { count: number }) =>
    options ? `${key}:${options.count}` : key;

  it("resolveDailyGoal falls back to default", () => {
    expect(resolveDailyGoal(null)).toBe(10);
    expect(resolveDailyGoal(5)).toBe(5);
  });

  it("formatDailyGoalLabel picks vocab vs trivia keys", () => {
    expect(formatDailyGoalLabel(5, "language", t)).toBe("projects.daily_goal_words:5");
    expect(formatDailyGoalLabel(5, "trivia", t)).toBe("projects.trivia.daily_questions:5");
  });

  it("dailyGoalPickerOptions lists all batch sizes", () => {
    const options = dailyGoalPickerOptions("language", t);
    expect(options).toHaveLength(VOCAB_DAILY_GOALS.length);
    expect(options.map((row) => row.key)).toEqual(["5", "10", "15"]);
  });
});
