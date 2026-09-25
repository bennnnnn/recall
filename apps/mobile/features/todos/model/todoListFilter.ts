import type { Todo } from "@/lib/api";
import { localDateKey } from "@/features/todos/model/dateKey";

export type TodoView = "all" | "open" | "completed" | "today";

/** Narrow the list for the header menu. Today is open items due today. */
export function todosForView(todos: Todo[], view: TodoView, now = new Date()): Todo[] {
  if (view === "completed") return todos.filter((todo) => todo.checked);
  if (view === "open") return todos.filter((todo) => !todo.checked);
  if (view === "today") {
    const today = localDateKey(now);
    return todos.filter((todo) => {
      if (todo.checked || !todo.due_at) return false;
      const due = new Date(todo.due_at);
      return Number.isFinite(due.getTime()) && localDateKey(due) === today;
    });
  }
  return todos;
}
