import {
  needsRecurrenceAdvance,
  nextRecurringDue,
  snapFirstDue,
} from "@/lib/todos/recurrence";

describe("schedule recurrence", () => {
  it("advances a past daily due to the next future morning", () => {
    const due = new Date(2026, 7, 20, 8, 0, 0);
    const now = new Date(2026, 7, 22, 9, 0, 0);
    const next = nextRecurringDue(due, "daily", now);
    expect(next.getFullYear()).toBe(2026);
    expect(next.getMonth()).toBe(7);
    expect(next.getDate()).toBe(23);
    expect(next.getHours()).toBe(8);
  });

  it("skips weekends for weekday repeats", () => {
    const friday = new Date(2026, 7, 21, 8, 0, 0); // Friday
    const saturday = new Date(2026, 7, 22, 9, 0, 0);
    const next = nextRecurringDue(friday, "weekdays", saturday);
    expect(next.getDay()).toBe(1);
    expect(next.getDate()).toBe(24);
  });

  it("snaps a Saturday first fire to Monday", () => {
    const saturday = new Date(2026, 7, 22, 8, 0, 0);
    const snapped = snapFirstDue(saturday, "weekdays");
    expect(snapped.getDay()).toBe(1);
  });

  it("does not advance a future due", () => {
    const due = new Date(2026, 8, 1, 8, 0, 0);
    const now = new Date(2026, 7, 20, 8, 0, 0);
    expect(needsRecurrenceAdvance(due.toISOString(), "weekly", false, now)).toBe(
      false,
    );
    expect(nextRecurringDue(due, "weekly", now).getTime()).toBe(due.getTime());
  });
});
