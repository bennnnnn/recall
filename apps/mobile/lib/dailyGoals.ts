/** Daily batch sizes for English vocabulary learning. */
export const VOCAB_DAILY_GOALS = [5, 10, 15] as const;

export type VocabDailyGoal = (typeof VOCAB_DAILY_GOALS)[number];

export const DEFAULT_VOCAB_DAILY_GOAL: VocabDailyGoal = 10;

export function resolveDailyGoal(value: number | null | undefined): number {
  if (value != null && value >= 1) return value;
  return DEFAULT_VOCAB_DAILY_GOAL;
}

export function formatDailyGoalLabel(
  goal: number,
  kind: "language" | "trivia",
  t: (key: string, options?: { count: number }) => string,
): string {
  return kind === "trivia"
    ? t("projects.trivia.daily_questions", { count: goal })
    : t("projects.daily_goal_words", { count: goal });
}

/** Compact display for learning settings rows and pickers (5, 10, 15). */
export function formatDailyGoalShort(goal: number): string {
  return String(goal);
}

export function dailyGoalPickerOptions(
  _kind: "language" | "trivia",
  _t: (key: string, options?: { count: number }) => string,
): { key: string; label: string }[] {
  return VOCAB_DAILY_GOALS.map((count) => ({
    key: String(count),
    label: formatDailyGoalShort(count),
  }));
}
