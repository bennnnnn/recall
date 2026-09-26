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
    project_id: null,
    created_at: `2026-09-0${id.length}T08:00:00.000Z`,
    updated_at: `2026-09-0${id.length}T09:00:00.000Z`,
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

  expect(rows.map((row) => row.kind === "heading"
    ? row.section
    : row.kind === "todo"
      ? row.todo.id
      : row.reminder.id,
  )).toEqual([
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

it("puts actionable email suggestions before the dated list", () => {
  const rows = buildTodoListRows(
    [todo("today", new Date(2026, 8, 22, 17).toISOString())],
    new Date(2026, 8, 22, 12),
    [{
      id: "suggestion-1",
      title: "Reply to recruiter",
      due_at: null,
      notes: null,
      confidence: 0.9,
      source_snippet: null,
      source_sender: "recruiter@example.com",
      status: "pending",
      created_at: "2026-09-22T08:00:00.000Z",
      gmail_message_id: "gmail-1",
    }],
  );

  expect(rows.slice(0, 2)).toMatchObject([
    { kind: "heading", section: "suggested", count: 1 },
    { kind: "suggestion", reminder: { id: "suggestion-1" } },
  ]);
});
