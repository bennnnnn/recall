/** Daily batch sizes for English vocabulary learning. */
export const VOCAB_DAILY_GOALS = [5, 10, 15] as const;

export type VocabDailyGoal = (typeof VOCAB_DAILY_GOALS)[number];

export const DEFAULT_VOCAB_DAILY_GOAL: VocabDailyGoal = 10;

export function resolveDailyGoal(value: number | null | undefined): number {
  if (value != null && value >= 1) return value;
  return DEFAULT_VOCAB_DAILY_GOAL;
}
