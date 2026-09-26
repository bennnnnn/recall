import { todosForView } from "@/features/todos/model/todoListFilter";
import type { Todo } from "@/lib/api";

function todo(partial: Partial<Todo> & Pick<Todo, "id">): Todo {
  return {
    content: partial.id,
    topic: "General",
    checked: false,
    due_at: null,
    sort_order: null,
    chat_id: null,
    created_at: "2026-09-01T00:00:00.000Z",
    updated_at: "2026-09-01T00:00:00.000Z",
    ...partial,
  };
}

const now = new Date(2026, 8, 25, 12, 0, 0);

describe("todosForView", () => {
  const rows = [
    todo({ id: "open", due_at: "2026-09-26T16:00:00.000Z" }),
    todo({ id: "today", due_at: new Date(2026, 8, 25, 15, 0, 0).toISOString() }),
    todo({ id: "done", checked: true, due_at: new Date(2026, 8, 25, 9, 0, 0).toISOString() }),
    todo({ id: "anytime" }),
  ];

  it("keeps every to-do on all", () => {
    expect(todosForView(rows, "all", now).map((item) => item.id)).toEqual([
      "open",
      "today",
      "done",
      "anytime",
    ]);
  });

  it("splits open and completed", () => {
    expect(todosForView(rows, "open", now).map((item) => item.id)).toEqual([
      "open",
      "today",
      "anytime",
    ]);
    expect(todosForView(rows, "completed", now).map((item) => item.id)).toEqual(["done"]);
  });

  it("previews only open to-dos due today", () => {
    expect(todosForView(rows, "today", now).map((item) => item.id)).toEqual(["today"]);
  });
});