import {
  formatClockTime,
  formatLongWeekdayDate,
  formatMinuteOfDay,
  formatMonthDayYear,
  formatShortWeekdayDate,
} from "@/lib/datetime/format";

describe("locale-aware date and time formatting", () => {
  const date = new Date(2026, 8, 8, 17, 5);

  it.each([
    ["clock time", () => formatClockTime(date, "en-US"), "5:05 PM"],
    ["minute of day", () => formatMinuteOfDay(330, "en-US"), "5:30 AM"],
    ["short weekday date", () => formatShortWeekdayDate(date, "en-US"), "Tue, Sep 8"],
    ["long weekday date", () => formatLongWeekdayDate(date, false, "en-US"), "Tuesday, September 8"],
    ["long weekday date with year", () => formatLongWeekdayDate(date, true, "en-US"), "Tuesday, September 8, 2026"],
    ["month day and year", () => formatMonthDayYear(date, "en-US"), "Sep 8, 2026"],
  ])("formats %s", (_label, format, expected) => {
    expect(format()).toBe(expected);
  });

  it("uses the requested locale", () => {
    expect(formatShortWeekdayDate(date, "de-DE")).toBe("Di., 8. Sept.");
  });
});
