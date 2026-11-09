import { localDayKey, utcDayKey } from "@/lib/datetime/dayKey";

describe("localDayKey", () => {
  it("is the phone's own day, zero-padded so it sorts as text", () => {
    // The export's file was "recall-export-1794113219708"; the plans offer kept "2026-1-3".
    expect(localDayKey(new Date(2026, 10, 7, 23, 59))).toBe("2026-11-07");
    expect(localDayKey(new Date(2027, 0, 3, 0, 1))).toBe("2027-01-03");
    expect(localDayKey(new Date(2026, 8, 30)) < localDayKey(new Date(2026, 9, 1))).toBe(true);
  });
});

describe("utcDayKey", () => {
  it("is the server's day, whatever the phone's zone", () => {
    expect(utcDayKey(new Date(Date.UTC(2026, 10, 7, 23, 59)))).toBe("2026-11-07");
    expect(utcDayKey(new Date(Date.UTC(2026, 10, 8, 0, 1)))).toBe("2026-11-08");
  });
});
