type Locale = string | string[] | undefined;

/** Device-locale clock time with the app's established hour/minute shape. */
export function formatClockTime(date: Date, locale?: Locale): string {
  return date.toLocaleTimeString(locale, {
    hour: "numeric",
    minute: "2-digit",
  });
}

/** Local-time clock label for a minute offset after midnight. */
export function formatMinuteOfDay(minutes: number, locale?: Locale): string {
  const date = new Date();
  date.setHours(Math.floor(minutes / 60), minutes % 60, 0, 0);
  return formatClockTime(date, locale);
}

/** Short weekday plus abbreviated month and numeric day. */
export function formatShortWeekdayDate(date: Date, locale?: Locale): string {
  return date.toLocaleDateString(locale, {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}

/** Long weekday plus long month and numeric day, with an optional year. */
export function formatLongWeekdayDate(
  date: Date,
  includeYear = false,
  locale?: Locale,
): string {
  return date.toLocaleDateString(locale, {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: includeYear ? "numeric" : undefined,
  });
}

/** Abbreviated month and numeric day ("Aug 30"). */
export function formatMonthDay(date: Date, locale?: Locale): string {
  return date.toLocaleDateString(locale, { month: "short", day: "numeric" });
}

/** Abbreviated month, numeric day, and numeric year. */
export function formatMonthDayYear(date: Date, locale?: Locale): string {
  return date.toLocaleDateString(locale, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}
