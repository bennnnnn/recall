import type { GoogleCalendarEvent, SuggestedReminder, Todo } from "@/lib/api";

/** Flattened row model for the Schedule screen's virtualized day body. */
export type ScheduleRow =
  | { kind: "suggestionsHeading" }
  | { kind: "suggestion"; reminder: SuggestedReminder }
  | { kind: "dayHeading"; heading: string }
  | { kind: "emptyDay" }
  | { kind: "meeting"; event: GoogleCalendarEvent }
  | { kind: "reminder"; todo: Todo };

export function scheduleRowKey(row: ScheduleRow): string {
  switch (row.kind) {
    case "suggestionsHeading":
      return "suggestions-heading";
    case "suggestion":
      return `suggestion-${row.reminder.id}`;
    case "dayHeading":
      return "day-heading";
    case "emptyDay":
      return "empty-day";
    case "meeting":
      return `meeting-${row.event.id}`;
    case "reminder":
      return `reminder-${row.todo.id}`;
  }
}

export function buildScheduleRows({
  selectedDaySuggestions,
  selectedDayHeading,
  selectedDayMeetings,
  selectedDayReminders,
}: {
  selectedDaySuggestions: SuggestedReminder[];
  selectedDayHeading: string;
  selectedDayMeetings: GoogleCalendarEvent[];
  selectedDayReminders: Todo[];
}): ScheduleRow[] {
  const rows: ScheduleRow[] = [];
  for (const reminder of selectedDaySuggestions) {
    rows.push({ kind: "suggestion", reminder });
  }
  if (selectedDaySuggestions.length > 0) {
    rows.unshift({ kind: "suggestionsHeading" });
  }
  rows.push({ kind: "dayHeading", heading: selectedDayHeading });
  if (
    selectedDayMeetings.length === 0 &&
    selectedDayReminders.length === 0 &&
    selectedDaySuggestions.length === 0
  ) {
    rows.push({ kind: "emptyDay" });
    return rows;
  }
  for (const event of selectedDayMeetings) {
    rows.push({ kind: "meeting", event });
  }
  for (const todo of selectedDayReminders) {
    rows.push({ kind: "reminder", todo });
  }
  return rows;
}
