import type { Todo } from "@/lib/api";
import { buildTodoListRows } from "@/features/todos/model/todoListRows";

function todo(id: string, dueAt: string | null, checked = false): Todo {
  return {
    id,
    content: id,
    topic: "General",
    checked,
    due_at: dueAt,
    recurrence_rule: null,
    sort_order: null,
    chat_id: null,
    created_at: `2026-09-0${id.length}T08:00:00.000Z`,
    updated_at: `2026-09-0${id.length}T09:00:00.000Z`,
    notify_at: null,
  };
}

it("groups dated and plain to-dos into a single urgency-ordered list", () => {
  const now = new Date(2026, 8, 22, 12, 0, 0);
  const rows = buildTodoListRows([
    todo("overdue", new Date(2026, 8, 21, 9).toISOString()),
    todo("today", new Date(2026, 8, 22, 17).toISOString()),
    todo("tomorrow", new Date(2026, 8, 23, 10).toISOString()),
    todo("future", new Date(2026, 8, 25, 10).toISOString()),
    todo("plain", null),
    todo("done", null, true),
  ], now);

  expect(rows.map((row) => (row.kind === "heading" ? row.section : row.todo.id))).toEqual([
    "overdue",
    "overdue",
    "today",
    "today",
    "tomorrow",
    "tomorrow",
    "date",
    "future",
    "anytime",
    "plain",
    "completed",
    "done",
  ]);
});

it("treats an invalid due date as an anytime to-do", () => {
  const rows = buildTodoListRows([todo("invalid", "not-a-date")], new Date(2026, 8, 22));
  expect(rows).toMatchObject([
    { kind: "heading", section: "anytime", count: 1 },
    { kind: "todo", todo: { id: "invalid" } },
  ]);
});

// A later day took each of its to-dos by copying the day so far, and every comparison
// parsed both due dates: 20,000 to-dos on one day took 1.5-1.8 s (jest), now 40-100 ms.
it("lists a very busy day in one pass", () => {
  const now = new Date(2026, 8, 22, 9);
  const busy = Array.from({ length: 20_000 }, (_, i) =>
    todo(`t${i}`, new Date(2026, 8, 25, 9, i % 600).toISOString()));
  const start = performance.now();
  const rows = buildTodoListRows(busy, now);
  expect(performance.now() - start).toBeLessThan(400);
  expect(rows).toHaveLength(20_001);
  expect(rows[0]).toMatchObject({ kind: "heading", section: "date", count: 20_000 });
  expect(rows[1]).toMatchObject({ kind: "todo", todo: { due_at: new Date(2026, 8, 25, 9, 0).toISOString() } });
});
