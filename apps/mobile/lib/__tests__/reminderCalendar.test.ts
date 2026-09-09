import {
  formatCalendarEventTime,
  weekdayHeaders,
} from "@/lib/todos/reminderCalendar";
import type { GoogleCalendarEvent } from "@/lib/api";

function event(partial: Partial<GoogleCalendarEvent>): GoogleCalendarEvent {
  return {
    id: "evt-1",
    calendar_name: "Work",
    title: "Standup",
    start_at: "2026-09-08T15:00:00.000Z",
    end_at: "2026-09-08T15:30:00.000Z",
    all_day: false,
    ...partial,
  };
}

describe("reminderCalendar copy", () => {
  it("uses the all-day i18n string", () => {
    expect(formatCalendarEventTime(event({ all_day: true }))).toBe("All day");
  });

  it("returns translated weekday shorts in Sunday-first order", () => {
    expect(weekdayHeaders().map((day) => `${day.id}:${day.label}`)).toEqual([
      "sun:Su",
      "mon:Mo",
      "tue:Tu",
      "wed:We",
      "thu:Th",
      "fri:Fr",
      "sat:Sa",
    ]);
  });
});
