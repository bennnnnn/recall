/**
 * Month grid, week start and year range for the date picker (`ui/pickers`).
 * Months are 0-based like `Date`. Days compare by calendar date, never time.
 */

import { formatDate, userWeekStart } from "@/lib/datetime/format";
import type { Weekday } from "@/lib/datetime/phoneClock";

type Locale = string | string[] | undefined;

export type YearMonth = { year: number; month: number };

/** Every grid has six weeks so the dialog keeps its height between months. */
const GRID_WEEKS = 6;

/** Regions whose week starts on Sunday or Saturday (CLDR week data). The rest start Monday. */
const SUNDAY_REGIONS = new Set(
  (
    "AG AS BD BR BS BT BW BZ CA CO DM DO ET GT GU HK HN ID IL IN JM JP KE KH KR LA MH MM " +
    "MO MT MX MZ NI NP PA PE PH PK PR PT PY SA SG SV TH TT TW UM US VE VI WS YE ZA ZW"
  ).split(" "),
);
const SATURDAY_REGIONS = new Set(
  "AE AF BH DJ DZ EG IQ IR JO KW LY OM QA SD SY".split(" "),
);
/** When a locale names no region, the region most of its speakers use. */
const LANGUAGE_REGION: Record<string, string> = { en: "US", am: "ET", pt: "BR", he: "IL", ja: "JP", ko: "KR" };

export function daysInMonth(year: number, month: number): number {
  return new Date(year, month + 1, 0).getDate();
}

/**
 * Six weeks of day numbers for `month`, starting on `weekStart`. Days from the
 * neighbouring months are null (the picker leaves those cells empty).
 */
export function monthGrid(year: number, month: number, weekStart: Weekday): (number | null)[][] {
  const lead = (new Date(year, month, 1).getDay() - weekStart + 7) % 7;
  const total = daysInMonth(year, month);
  const cells: (number | null)[] = [];
  for (let i = 0; i < GRID_WEEKS * 7; i++) {
    const day = i - lead + 1;
    cells.push(day >= 1 && day <= total ? day : null);
  }
  const weeks: (number | null)[][] = [];
  for (let w = 0; w < GRID_WEEKS; w++) weeks.push(cells.slice(w * 7, w * 7 + 7));
  return weeks;
}

export function addMonths(at: YearMonth, delta: number): YearMonth {
  const index = at.year * 12 + at.month + delta;
  return { year: Math.floor(index / 12), month: ((index % 12) + 12) % 12 };
}

/** Negative, zero or positive as `a` falls before, on or after `b`'s calendar day. */
export function compareDays(a: Date, b: Date): number {
  return (
    a.getFullYear() - b.getFullYear() ||
    a.getMonth() - b.getMonth() ||
    a.getDate() - b.getDate()
  );
}

export function isSameDay(a: Date, b: Date): boolean {
  return compareDays(a, b) === 0;
}

/** `date` on another calendar day, keeping the time of day. */
export function withDay(date: Date, at: YearMonth, day: number): Date {
  const next = new Date(date.getTime());
  next.setFullYear(at.year, at.month, day);
  return next;
}

/** Years the year grid lists: a century back and fifty ahead, always with `selected`. */
export function yearRange(selected: number, now = new Date()): number[] {
  const first = Math.min(selected, now.getFullYear() - 100);
  const last = Math.max(selected, now.getFullYear() + 50);
  const years: number[] = [];
  for (let year = first; year <= last; year++) years.push(year);
  return years;
}

function localeRegion(locale?: Locale): { language: string; region: string | null } {
  let tag = Array.isArray(locale) ? locale[0] : locale;
  if (!tag) {
    try {
      tag = new Intl.DateTimeFormat().resolvedOptions().locale;
    } catch {
      tag = "en-US";
    }
  }
  const parts = tag.split(/[-_]/);
  const language = parts[0].toLowerCase();
  const region = parts.slice(1).find((part) => /^[A-Za-z]{2}$|^\d{3}$/.test(part));
  return { language, region: region ? region.toUpperCase() : null };
}

/**
 * First day of the week: the phone's own setting when `locale` is omitted and the phone
 * says; otherwise where `locale` (the device's when omitted) is used.
 */
export function firstDayOfWeek(locale?: Locale): Weekday {
  const phone = locale === undefined ? userWeekStart() : undefined;
  if (phone !== undefined) return phone;
  const { language, region } = localeRegion(locale);
  const place = region ?? LANGUAGE_REGION[language] ?? "";
  if (SUNDAY_REGIONS.has(place)) return 0;
  if (SATURDAY_REGIONS.has(place)) return 6;
  return 1;
}

/** One letter and the full name for each weekday column, starting on `weekStart`. */
export function weekdayLabels(weekStart: Weekday): { narrow: string; long: string }[] {
  const labels: { narrow: string; long: string }[] = [];
  for (let i = 0; i < 7; i++) {
    // 2023-01-01 was a Sunday.
    const date = new Date(2023, 0, 1 + ((weekStart + i) % 7));
    labels.push({ narrow: formatDate(date, "narrowWeekday"), long: formatDate(date, "longWeekday") });
  }
  return labels;
}

/** "September 2026". */
export function monthYearLabel(at: YearMonth): string {
  return formatDate(new Date(at.year, at.month, 1), "monthYear");
}
