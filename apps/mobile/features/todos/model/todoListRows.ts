import type { SuggestedReminder, Todo } from "@/lib/api";
import { localDateKey } from "@/features/todos/model/dateKey";

export type TodoSection =
  | "suggested"
  | "overdue"
  | "today"
  | "tomorrow"
  | "date"
  | "anytime"
  | "completed";

export type TodoListRow =
  | { kind: "heading"; section: TodoSection; key: string; dayKey?: string; count: number }
  | { kind: "suggestion"; reminder: SuggestedReminder }
  | { kind: "todo"; todo: Todo };

export function todoListRowKey(row: TodoListRow): string {
  if (row.kind === "todo") return `todo-${row.todo.id}`;
  if (row.kind === "suggestion") return `suggestion-${row.reminder.id}`;
  return `heading-${row.key}`;
}

function sortByDueThenCreated(a: Todo, b: Todo): number {
  const aDue = a.due_at ? new Date(a.due_at).getTime() : Number.POSITIVE_INFINITY;
  const bDue = b.due_at ? new Date(b.due_at).getTime() : Number.POSITIVE_INFINITY;
  if (aDue !== bDue) return aDue - bDue;
  return b.created_at.localeCompare(a.created_at);
}

function appendGroup(
  rows: TodoListRow[],
  section: TodoSection,
  key: string,
  items: Todo[],
  dayKey?: string,
): void {
  if (!items.length) return;
  rows.push({ kind: "heading", section, key, dayKey, count: items.length });
  rows.push(...items.map((todo) => ({ kind: "todo" as const, todo })));
}

/** Build one urgency-ordered list, separated into readable day groups. */
export function buildTodoListRows(
  todos: Todo[],
  now = new Date(),
  suggestions: SuggestedReminder[] = [],
): TodoListRow[] {
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const tomorrow = new Date(today);
  tomorrow.setDate(tomorrow.getDate() + 1);
  const todayKey = localDateKey(today);
  const tomorrowKey = localDateKey(tomorrow);
  const overdue: Todo[] = [];
  const todayItems: Todo[] = [];
  const tomorrowItems: Todo[] = [];
  const anytime: Todo[] = [];
  const completed: Todo[] = [];
  const futureByDay = new Map<string, Todo[]>();

  for (const todo of todos) {
    if (todo.checked) {
      completed.push(todo);
      continue;
    }
    if (!todo.due_at) {
      anytime.push(todo);
      continue;
    }
    const due = new Date(todo.due_at);
    if (!Number.isFinite(due.getTime())) {
      anytime.push(todo);
      continue;
    }
    const dayKey = localDateKey(due);
    if (dayKey < todayKey) overdue.push(todo);
    else if (dayKey === todayKey) todayItems.push(todo);
    else if (dayKey === tomorrowKey) tomorrowItems.push(todo);
    else futureByDay.set(dayKey, [...(futureByDay.get(dayKey) ?? []), todo]);
  }

  const rows: TodoListRow[] = [];
  if (suggestions.length) {
    rows.push({ kind: "heading", section: "suggested", key: "suggested", count: suggestions.length });
    rows.push(...suggestions.map((reminder) => ({ kind: "suggestion" as const, reminder })));
  }
  appendGroup(rows, "overdue", "overdue", overdue.sort(sortByDueThenCreated));
  appendGroup(rows, "today", todayKey, todayItems.sort(sortByDueThenCreated), todayKey);
  appendGroup(
    rows,
    "tomorrow",
    tomorrowKey,
    tomorrowItems.sort(sortByDueThenCreated),
    tomorrowKey,
  );
  for (const [dayKey, items] of [...futureByDay].sort(([a], [b]) => a.localeCompare(b))) {
    appendGroup(rows, "date", dayKey, items.sort(sortByDueThenCreated), dayKey);
  }
  appendGroup(
    rows,
    "anytime",
    "anytime",
    anytime.sort((a, b) => b.created_at.localeCompare(a.created_at)),
  );
  appendGroup(
    rows,
    "completed",
    "completed",
    completed.sort((a, b) => b.updated_at.localeCompare(a.updated_at)),
  );
  return rows;
}
