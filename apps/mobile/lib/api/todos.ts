import { request } from "@/lib/api/client";
import type { Todo } from "@/lib/api/types";

const TODO_PAGE_SIZE = 1000;

async function listTodos(token: string, options?: { signal?: AbortSignal }): Promise<Todo[]> {
  const rows = new Map<string, Todo>();
  for (let offset = 0; ; offset += TODO_PAGE_SIZE) {
    const page = await request<Todo[]>(`/todos?limit=${TODO_PAGE_SIZE}&offset=${offset}`, token, options);
    const previousSize = rows.size;
    page.forEach((row) => rows.set(row.id, row));
    if (page.length < TODO_PAGE_SIZE) return [...rows.values()];
    if (rows.size === previousSize) throw new Error("Todo pagination did not advance");
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
