const WEEKDAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const;

export type WeekdayKey = (typeof WEEKDAY_KEYS)[number];

export function weekdayKey(weekday: number): WeekdayKey {
  return WEEKDAY_KEYS[weekday] ?? "mon";
}

/** Short label for the calendar strip (M, T, W, …). */
export function weekdayShortLabel(
  weekday: number,
  t: (key: string) => string,
): string {
  return t(`projects.daily_strip.${weekdayKey(weekday)}`);
}

/** Full day name for detail headers (Monday, Tuesday, …). */
export function weekdayFullLabel(
  weekday: number,
  t: (key: string) => string,
): string {
  return t(`projects.weekday_full.${weekdayKey(weekday)}`);
}
