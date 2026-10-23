import {
  formatClockTime,
  formatMinuteOfDay,
  formatMonthDayYear,
  formatShortWeekdayDate,
  formatTimeZoneName,
} from "@/lib/datetime/format";

describe("locale-aware date and time formatting", () => {
  const date = new Date(2026, 8, 8, 17, 5);

  it.each([
    ["clock time", () => formatClockTime(date, "en-US"), "5:05 PM"],
    ["minute of day", () => formatMinuteOfDay(330, "en-US"), "5:30 AM"],
    ["short weekday date", () => formatShortWeekdayDate(date, "en-US"), "Tue, Sep 8"],
    ["month day and year", () => formatMonthDayYear(date, "en-US"), "Sep 8, 2026"],
  ])("formats %s", (_label, format, expected) => {
    expect(format()).toBe(expected);
  });

  it("uses the requested locale", () => {
    expect(formatShortWeekdayDate(date, "de-DE")).toBe("Di., 8. Sept.");
  });
});

describe("formatTimeZoneName", () => {
  const instant = new Date(Date.UTC(2026, 9, 24, 6, 0));

  it.each([
    ["America/New_York", "EDT"],
    ["UTC", "UTC"],
  ])("names %s as %s", (zone, name) => {
    expect(formatTimeZoneName(instant, zone, "en-US")).toBe(name);
  });

  it("returns null for an unknown zone", () => {
    expect(formatTimeZoneName(instant, "Not/AZone", "en-US")).toBeNull();
  });

  describe("when the engine names an offset zone plain GMT (Hermes)", () => {
    const real = Intl.DateTimeFormat.prototype.formatToParts;
    beforeEach(() => {
      jest
        .spyOn(Intl.DateTimeFormat.prototype, "formatToParts")
        .mockImplementation(function (this: Intl.DateTimeFormat, ...args) {
          return real
            .apply(this, args)
            .map((part) => (part.type === "timeZoneName" ? { ...part, value: "GMT" } : part));
        });
    });
    afterEach(() => jest.restoreAllMocks());

    it.each([
      ["Africa/Nairobi", "GMT+3"],
      ["Asia/Kolkata", "GMT+5:30"],
      ["America/Los_Angeles", "GMT-7"],
      ["Europe/London", "GMT+1"],
      ["Atlantic/Reykjavik", "GMT"],
    ])("gives %s its offset, %s", (zone, label) => {
      expect(formatTimeZoneName(instant, zone, "en-US")).toBe(label);
    });
  });
});
