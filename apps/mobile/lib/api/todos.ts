import { request } from "@/lib/api/client";
import type { Todo } from "@/lib/api/types";

const TODO_PAGE_SIZE = 1000;

type TodoPage = { items: Todo[]; next_cursor: string | null };

async function listTodos(token: string, options?: { signal?: AbortSignal }): Promise<Todo[]> {
  const rows = new Map<string, Todo>();
  const visitedCursors = new Set<string>();
  let cursor: string | null = null;
  for (;;) {
    const suffix: string = cursor === null ? "" : `&cursor=${encodeURIComponent(cursor)}`;
    const page: TodoPage = await request<TodoPage>(`/todos/page?limit=${TODO_PAGE_SIZE}${suffix}`, token, options);
    page.items.forEach((row) => rows.set(row.id, row));
    if (page.next_cursor === null) return [...rows.values()];
    if (visitedCursors.has(page.next_cursor)) throw new Error("Todo pagination did not advance");
    visitedCursors.add(page.next_cursor);
    cursor = page.next_cursor;
  }
}

export const todosApi = {
  listTodos,
  createTodo: (
    token: string,
    content: string,
    topic = "General",
    options?: {
      chatId?: string;
      projectId?: string | null;
      dueAt?: string | null;
      recurrenceRule?: Todo["recurrence_rule"];
    },
  ) =>
    request<Todo>("/todos", token, {
      method: "POST",
      body: JSON.stringify({
        content,
        topic,
        chat_id: options?.chatId ?? null,
        project_id: options?.projectId ?? undefined,
        due_at: options?.dueAt ?? undefined,
        recurrence_rule: options?.recurrenceRule ?? undefined,
      }),
    }),
  updateTodo: (
    token: string,
    id: string,
    patch: Partial<
      Pick<
        Todo,
        | "content"
        | "topic"
        | "checked"
        | "due_at"
        | "recurrence_rule"
        | "sort_order"
        | "project_id"
      >
    >,
  ) =>
    request<Todo>(`/todos/${id}`, token, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),
  deleteTodo: (token: string, id: string) =>
    request<void>(`/todos/${id}`, token, { method: "DELETE" }),
};
