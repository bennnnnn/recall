import type { Todo } from "@/lib/api/types";
import { localDayKey } from "@/lib/datetime/dayKey";
import { dueOfTodo } from "@/features/todos/model/dueDate";

export type TodoView = "all" | "open" | "completed" | "today";

/** Completed to-dos older than this stay on the server until the list asks for them. */
export const RECENT_COMPLETED_DAYS = 30;

/** Narrow the list for the header menu. Today is open items due today or overdue. */
export function todosForView(todos: Todo[], view: TodoView, now = new Date()): Todo[] {
  if (view === "completed") return todos.filter((todo) => todo.checked);
  if (view === "open") return todos.filter((todo) => !todo.checked);
  if (view === "today") {
    const today = localDayKey(now);
    return todos.filter((todo) => {
      const due = todo.checked ? null : dueOfTodo(todo);
      return due !== null && localDayKey(due.date) <= today;
    });
  }
  return todos;
}

/**
 * The view to show after adding a to-do due at `due`: this one when it lists the new item,
 * else "open". An undated or later to-do added on Today used to vanish from sight.
 */
export function viewForNewTodo(view: TodoView, due: Date | null, now = new Date()): TodoView {
  const added = { checked: false, due_at: due ? due.toISOString() : null } as Todo;
  return todosForView([added], view, now).length > 0 ? view : "open";
}
