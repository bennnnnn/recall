import type { Todo } from "@/lib/api";
import { DEFAULT_HOME_URGENT_LEAD } from "@/lib/homeUrgentTodos";

/**
 * Urgent = overdue OR due within the user's reminder lead (minutes). Unified
 * with the home urgent cards and local/server notifications, all driven by
 * `reminder_lead_minutes`. Replaces the former "overdue or any time later
 * today" calendar-day rule.
 */
function isUrgentReminder(todo: Todo, now: Date, leadMs: number): boolean {
  if (todo.checked || !todo.due_at) return false;
  const due = new Date(todo.due_at);
  if (Number.isNaN(due.getTime())) return false;
  const dueMs = due.getTime();
  if (dueMs < now.getTime()) return true; // overdue
  return dueMs <= now.getTime() + leadMs;
}

/** Open reminders that are overdue or due within the lead window. */
export function listUrgentReminders(
  todos: Todo[],
  now = new Date(),
  leadMinutes: number = DEFAULT_HOME_URGENT_LEAD,
): Todo[] {
  const leadMs = leadMinutes * 60_000;
  return todos.filter((todo) => isUrgentReminder(todo, now, leadMs));
}

export function listUrgentReminderIds(
  todos: Todo[],
  now = new Date(),
  leadMinutes: number = DEFAULT_HOME_URGENT_LEAD,
): string[] {
  return listUrgentReminders(todos, now, leadMinutes).map((todo) => todo.id);
}

/** Open reminders that are overdue or due within the lead window. */
export function countUrgentReminders(
  todos: Todo[],
  now = new Date(),
  leadMinutes: number = DEFAULT_HOME_URGENT_LEAD,
): number {
  return listUrgentReminders(todos, now, leadMinutes).length;
}

export function countUnseenUrgentReminders(
  todos: Todo[],
  seenIds: Set<string>,
  now = new Date(),
  leadMinutes: number = DEFAULT_HOME_URGENT_LEAD,
): number {
  return listUrgentReminders(todos, now, leadMinutes).filter(
    (todo) => !seenIds.has(todo.id),
  ).length;
}
