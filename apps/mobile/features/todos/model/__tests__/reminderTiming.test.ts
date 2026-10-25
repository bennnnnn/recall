import {
  DEFAULT_REMINDER_LEAD_MINUTES,
  normalizeReminderLeadMinutes,
  remindAtDate,
} from "@/features/todos/model/reminderTiming";

describe("reminderTiming", () => {
  it("normalizes lead minutes to allowed values", () => {
    expect(normalizeReminderLeadMinutes(15)).toBe(15);
    expect(normalizeReminderLeadMinutes("30")).toBe(30);
    expect(normalizeReminderLeadMinutes(60)).toBe(60);
    expect(normalizeReminderLeadMinutes(99)).toBe(DEFAULT_REMINDER_LEAD_MINUTES);
  });

  it("places remind-at at due minus the settings lead", () => {
    const due = new Date("2026-06-28T20:00:00.000Z");
    expect(remindAtDate(due, 5).toISOString()).toBe("2026-06-28T19:55:00.000Z");
    expect(remindAtDate(due, 99).toISOString()).toBe("2026-06-28T19:50:00.000Z");
  });
});
