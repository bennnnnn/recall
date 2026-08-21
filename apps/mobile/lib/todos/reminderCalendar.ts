import type { GoogleCalendarEvent, SuggestedReminder, Todo } from "@/lib/api";

/** Local calendar date `YYYY-MM-DD` (device timezone). */
export function localDateKey(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

export function parseDateKey(key: string): Date {
  const [y, m, d] = key.split("-").map(Number);
  return new Date(y, m - 1, d);
}

export function startOfMonth(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

export function addMonths(date: Date, delta: number): Date {
  return new Date(date.getFullYear(), date.getMonth() + delta, 1);
}

export type MonthCell = {
  key: string | null;
  day: number | null;
};

export function buildMonthCells(year: number, month: number): MonthCell[] {
  const first = new Date(year, month, 1);
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const cells: MonthCell[] = [];

  for (let i = 0; i < first.getDay(); i += 1) {
    cells.push({ key: null, day: null });
  }
  for (let day = 1; day <= daysInMonth; day += 1) {
    const date = new Date(year, month, day);
    cells.push({ key: localDateKey(date), day });
  }
  while (cells.length % 7 !== 0) {
    cells.push({ key: null, day: null });
  }
  return cells;
}

export function countRemindersByDay(reminders: Todo[]): Map<string, number> {
  const counts = new Map<string, number>();
  for (const todo of reminders) {
    if (!todo.due_at || todo.checked) continue;
    const key = localDateKey(new Date(todo.due_at));
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return counts;
}

export function countCalendarEventsByDay(events: GoogleCalendarEvent[]): Map<string, number> {
  const counts = new Map<string, number>();
  for (const event of events) {
    const key = localDateKey(new Date(event.start_at));
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return counts;
}

export function countSuggestedByDay(
  suggestions: SuggestedReminder[],
  todayKey = localDateKey(new Date()),
): Map<string, number> {
  const counts = new Map<string, number>();
  for (const item of suggestions) {
    if (item.status !== "pending") continue;
    const key = item.due_at ? localDateKey(new Date(item.due_at)) : todayKey;
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return counts;
}

export function suggestedRemindersOnDay(
  suggestions: SuggestedReminder[],
  dayKey: string,
  todayKey = localDateKey(new Date()),
): SuggestedReminder[] {
  return suggestions.filter((item) => {
    if (item.status !== "pending") return false;
    const key = item.due_at ? localDateKey(new Date(item.due_at)) : todayKey;
    return key === dayKey;
  });
}

export function mergeDayCounts(...maps: Map<string, number>[]): Map<string, number> {
  const merged = new Map<string, number>();
  for (const map of maps) {
    for (const [key, count] of map.entries()) {
      merged.set(key, (merged.get(key) ?? 0) + count);
    }
  }
  return merged;
}

export function calendarEventsOnDay(
  events: GoogleCalendarEvent[],
  dayKey: string,
): GoogleCalendarEvent[] {
  const onDay = events.filter(
    (event) => localDateKey(new Date(event.start_at)) === dayKey,
  );
  return [...onDay].sort(
    (a, b) => new Date(a.start_at).getTime() - new Date(b.start_at).getTime(),
  );
}

export function formatCalendarEventTime(event: GoogleCalendarEvent): string {
  if (event.all_day) return "All day";
  const start = new Date(event.start_at);
  const end = event.end_at ? new Date(event.end_at) : null;
  const time = (date: Date) =>
    date.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  if (end && end.getTime() > start.getTime()) {
    return `${time(start)} – ${time(end)}`;
  }
  return time(start);
}

export function remindersOnDay(reminders: Todo[], dayKey: string): Todo[] {
  const onDay = reminders.filter(
    (todo) => todo.due_at && localDateKey(new Date(todo.due_at)) === dayKey,
  );
  return [...onDay].sort((a, b) => {
    if (a.checked !== b.checked) return Number(a.checked) - Number(b.checked);
    const aDue = a.due_at ? new Date(a.due_at).getTime() : 0;
    const bDue = b.due_at ? new Date(b.due_at).getTime() : 0;
    if (aDue !== bDue) return aDue - bDue;
    return a.created_at.localeCompare(b.created_at);
  });
}

const WEEKDAYS = [
  { id: "sun", label: "Su" },
  { id: "mon", label: "Mo" },
  { id: "tue", label: "Tu" },
  { id: "wed", label: "We" },
  { id: "thu", label: "Th" },
  { id: "fri", label: "Fr" },
  { id: "sat", label: "Sa" },
] as const;

export function weekdayHeaders(): ReadonlyArray<{ id: string; label: string }> {
  return WEEKDAYS;
}

/** @deprecated Use weekdayHeaders() — narrow locale labels duplicate (T, S). */
export function weekdayLabels(): string[] {
  return WEEKDAYS.map((day) => day.label);
}

export function formatDayHeading(dayKey: string, now = new Date()): string {
  const date = parseDateKey(dayKey);
  const todayKey = localDateKey(now);
  const tomorrow = new Date(now);
  tomorrow.setDate(tomorrow.getDate() + 1);
  const tomorrowKey = localDateKey(tomorrow);

  if (dayKey === todayKey) {
    return date.toLocaleDateString(undefined, {
      weekday: "long",
      month: "long",
      day: "numeric",
    });
  }
  if (dayKey === tomorrowKey) {
    return date.toLocaleDateString(undefined, {
      weekday: "long",
      month: "long",
      day: "numeric",
    });
  }
  return date.toLocaleDateString(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: date.getFullYear() !== now.getFullYear() ? "numeric" : undefined,
  });
}
