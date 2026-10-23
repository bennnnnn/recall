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

/**
 * The zone's short name at that instant ("EDT", "GMT+3"), or null for an unknown zone.
 *
 * Hermes names a zone with no abbreviation (Africa/Nairobi) plain "GMT", which reads as
 * three hours off; a bare GMT or UTC for a zone that is not at zero gets its offset.
 */
export function formatTimeZoneName(date: Date, timeZone: string, locale?: Locale): string | null {
  try {
    const formatter = new Intl.DateTimeFormat(locale, { timeZone, timeZoneName: "short" });
    const parts = formatter.formatToParts(date);
    const name = parts.find((part) => part.type === "timeZoneName")?.value ?? null;
    if (name !== "GMT" && name !== "UTC") return name;
    const minutes = zoneOffsetMinutes(date, timeZone);
    return minutes === 0 ? name : offsetLabel(minutes);
  } catch {
    return null;
  }
}

/** Minutes the zone's wall clock is ahead of UTC at that instant. */
function zoneOffsetMinutes(date: Date, timeZone: string): number {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    hourCycle: "h23",
    year: "numeric",
    month: "numeric",
    day: "numeric",
    hour: "numeric",
    minute: "numeric",
  }).formatToParts(date);
  const get = (type: Intl.DateTimeFormatPartTypes) =>
    Number(parts.find((part) => part.type === type)?.value ?? 0);
  const wall = Date.UTC(get("year"), get("month") - 1, get("day"), get("hour"), get("minute"));
  const instant = Math.floor(date.getTime() / 60000) * 60000;
  return Math.round((wall - instant) / 60000);
}

function offsetLabel(minutes: number): string {
  const sign = minutes < 0 ? "-" : "+";
  const hours = Math.floor(Math.abs(minutes) / 60);
  const rest = Math.abs(minutes) % 60;
  return `GMT${sign}${hours}${rest ? `:${String(rest).padStart(2, "0")}` : ""}`;
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
