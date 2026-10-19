type Locale = string | string[] | undefined;

/**
 * Device-locale clock time with the app's established hour/minute shape, in the
 * phone's zone or the IANA `timeZone` given.
 */
export function formatClockTime(date: Date, locale?: Locale, timeZone?: string): string {
  return date.toLocaleTimeString(locale, {
    hour: "numeric",
    minute: "2-digit",
    timeZone,
  });
}

/** Local-time clock label for a minute offset after midnight. */
export function formatMinuteOfDay(minutes: number, locale?: Locale): string {
  const date = new Date();
  date.setHours(Math.floor(minutes / 60), minutes % 60, 0, 0);
  return formatClockTime(date, locale);
}

/** Short weekday plus abbreviated month and numeric day, in the phone's zone or `timeZone`. */
export function formatShortWeekdayDate(date: Date, locale?: Locale, timeZone?: string): string {
  return date.toLocaleDateString(locale, {
    weekday: "short",
    month: "short",
    day: "numeric",
    timeZone,
  });
}

/** The zone's short name at that instant ("EDT", "GMT+3"), or null for an unknown zone. */
export function formatTimeZoneName(date: Date, timeZone: string, locale?: Locale): string | null {
  try {
    const formatter = new Intl.DateTimeFormat(locale, { timeZone, timeZoneName: "short" });
    const parts = formatter.formatToParts(date);
    return parts.find((part) => part.type === "timeZoneName")?.value ?? null;
  } catch {
    return null;
  }
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
