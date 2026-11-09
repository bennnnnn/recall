import type { Todo } from "@/lib/api";
import { overdueAt } from "@/features/todos/model/dueDate";
import { listUrgentReminders } from "@/features/todos/model/reminderBadge";

/**
 * The one overdue reminder Home shows: an open reminder that has gone out (its `notify_at`
 * has come, the badge's rule), is overdue (past its time, or for a date alone past its
 * day) and was not dismissed, the longest
 * overdue first. Dismissed ones are left out before the pick: picking from the five oldest
 * first let five dismissals hide every later overdue reminder for good.
 */
export function firstOverdueHomeTodo(
  todos: Todo[],
  dismissed: ReadonlySet<string>,
  now = new Date(),
): Todo | undefined {
  const nowMs = now.getTime();
  return listUrgentReminders(todos, now)
    .filter((todo) => !dismissed.has(todo.id) && (overdueAt(todo) ?? Infinity) < nowMs)
    .sort((a, b) => Date.parse(a.due_at!) - Date.parse(b.due_at!))[0];
}
