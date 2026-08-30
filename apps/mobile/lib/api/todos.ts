import { request } from "@/lib/api/client";
import type { Todo } from "@/lib/api/types";

export const todosApi = {
  listTodos: (token: string) => request<Todo[]>("/todos", token),
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
        project_id: options?.projectId ?? null,
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
