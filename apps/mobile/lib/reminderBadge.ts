import type { Todo } from "@/lib/api";
import { localDateKey } from "@/lib/reminderCalendar";

function isUrgentReminder(todo: Todo, now: Date, todayKey: string): boolean {
  if (todo.checked || !todo.due_at) return false;
  const due = new Date(todo.due_at);
  if (Number.isNaN(due.getTime())) return false;
  if (due.getTime() < now.getTime()) return true;
  return localDateKey(due) === todayKey;
}

/** Open reminders that are overdue or due later today (device local time). */
export function listUrgentReminders(todos: Todo[], now = new Date()): Todo[] {
  const todayKey = localDateKey(now);
  return todos.filter((todo) => isUrgentReminder(todo, now, todayKey));
}

export function listUrgentReminderIds(todos: Todo[], now = new Date()): string[] {
  return listUrgentReminders(todos, now).map((todo) => todo.id);
}

/** Open reminders that are overdue or due later today (device local time). */
export function countUrgentReminders(todos: Todo[], now = new Date()): number {
  return listUrgentReminders(todos, now).length;
}

export function countUnseenUrgentReminders(
  todos: Todo[],
  seenIds: Set<string>,
  now = new Date(),
): number {
  return listUrgentReminders(todos, now).filter((todo) => !seenIds.has(todo.id)).length;
}
