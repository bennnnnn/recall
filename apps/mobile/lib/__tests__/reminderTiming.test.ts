import {
  DEFAULT_REMINDER_LEAD_MINUTES,
  IMMINENT_NOTIFY_DELAY_MS,
  isWithinReminderLeadWindow,
  leadMsFromMinutes,
  normalizeReminderLeadMinutes,
  reminderNotifyDate,
} from "@/lib/reminderTiming";

describe("reminderTiming", () => {
  const now = new Date("2026-06-28T12:00:00.000Z");

  it("normalizes lead minutes to allowed values", () => {
    expect(normalizeReminderLeadMinutes(15)).toBe(15);
    expect(normalizeReminderLeadMinutes("30")).toBe(30);
    expect(normalizeReminderLeadMinutes(99)).toBe(DEFAULT_REMINDER_LEAD_MINUTES);
  });

  it("schedules notify at due minus lead", () => {
    const due = new Date("2026-06-28T12:30:00.000Z");
    const notify = reminderNotifyDate(due, now, leadMsFromMinutes(10));
    expect(notify?.toISOString()).toBe("2026-06-28T12:20:00.000Z");
  });

  it("fires soon when due is inside the lead window", () => {
    const due = new Date("2026-06-28T12:05:00.000Z");
    const notify = reminderNotifyDate(due, now, leadMsFromMinutes(10));
    expect(notify?.getTime()).toBe(now.getTime() + IMMINENT_NOTIFY_DELAY_MS);
  });

  it("returns null for past due times", () => {
    const due = new Date("2026-06-28T11:00:00.000Z");
    expect(reminderNotifyDate(due, now, leadMsFromMinutes(10))).toBeNull();
  });

  it("respects each lead option", () => {
    const due = new Date("2026-06-28T13:00:00.000Z");
    for (const minutes of [5, 10, 15, 30] as const) {
      const notify = reminderNotifyDate(due, now, leadMsFromMinutes(minutes));
      expect(notify?.getTime()).toBe(due.getTime() - leadMsFromMinutes(minutes));
    }
  });

  it("detects lead windows for push scheduling", () => {
    const dueSoon = new Date("2026-06-28T12:04:00.000Z");
    const dueLater = new Date("2026-06-28T12:25:00.000Z");
    expect(isWithinReminderLeadWindow(dueSoon, now, 5)).toBe(true);
    expect(isWithinReminderLeadWindow(dueLater, now, 5)).toBe(false);
    expect(isWithinReminderLeadWindow(dueLater, now, 30)).toBe(true);
  });
});
