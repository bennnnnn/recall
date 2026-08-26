import type { RecurrenceRule, Todo } from "@/lib/api";

export const OPTIMISTIC_TODO_ID_PREFIX = "local-todo-";

let optimisticTodoSeq = 0;

export function newOptimisticTodoId(): string {
  optimisticTodoSeq += 1;
  return `${OPTIMISTIC_TODO_ID_PREFIX}${Date.now()}-${optimisticTodoSeq}`;
}

export function buildOptimisticTodo(fields: {
  content: string;
  topic: string;
  dueAt?: string | null;
  recurrenceRule?: RecurrenceRule | null;
  sortOrder?: number | null;
}): Todo {
  const now = new Date().toISOString();
  return {
    id: newOptimisticTodoId(),
    content: fields.content,
    topic: fields.topic,
    checked: false,
    due_at: fields.dueAt ?? null,
    recurrence_rule: fields.recurrenceRule ?? null,
    sort_order: fields.sortOrder ?? null,
    chat_id: null,
    project_id: null,
    created_at: now,
    updated_at: now,
  };
}

export function replaceTodoById(todos: Todo[], id: string, next: Todo): Todo[] {
  return todos.map((item) => (item.id === id ? next : item));
}

export function removeTodoById(todos: Todo[], id: string): Todo[] {
  return todos.filter((item) => item.id !== id);
}
