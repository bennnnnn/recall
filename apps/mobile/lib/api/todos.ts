import { request } from "@/lib/api/client";
import type { Todo } from "@/lib/api/types";

export const todosApi = {
  listTodos: (token: string) => request<Todo[]>("/todos", token),
  listTodoTopics: (token: string) => request<string[]>("/todos/topics", token),
  createTodo: (
    token: string,
    content: string,
    topic = "General",
    options?: { chatId?: string; projectId?: string | null; dueAt?: string | null },
  ) =>
    request<Todo>("/todos", token, {
      method: "POST",
      body: JSON.stringify({
        content,
        topic,
        chat_id: options?.chatId ?? null,
        project_id: options?.projectId ?? null,
        due_at: options?.dueAt ?? undefined,
      }),
    }),
  updateTodo: (
    token: string,
    id: string,
    patch: Partial<
      Pick<Todo, "content" | "topic" | "checked" | "due_at" | "sort_order" | "project_id">
    >,
  ) =>
    request<Todo>(`/todos/${id}`, token, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),
  reorderTodos: (
    token: string,
    items: { id: string; sort_order: number; topic?: string }[],
  ) =>
    request<Todo[]>("/todos/reorder", token, {
      method: "POST",
      body: JSON.stringify({ items }),
    }),
  deleteTodo: (token: string, id: string) =>
    request<void>(`/todos/${id}`, token, { method: "DELETE" }),
  deleteTodoTopic: (token: string, topic: string) =>
    request<void>(`/todos/topic/${encodeURIComponent(topic)}`, token, { method: "DELETE" }),
};
