import type { Todo } from "@/lib/api";
import { listUrgentReminders } from "@/features/todos/model/reminderBadge";

/**
 * The one overdue reminder Home shows: an open reminder that has gone out (its `notify_at`
 * has come, the badge's rule), is past its due time and was not dismissed, the longest
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
    .filter((todo) => !dismissed.has(todo.id) && Date.parse(todo.due_at!) < nowMs)
    .sort((a, b) => Date.parse(a.due_at!) - Date.parse(b.due_at!))[0];
}
