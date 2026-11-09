/**
 * A to-do can have a date and no time (`due_has_time` false). Picking a date used to write
 * a time with it, so a date alone showed a time, a Remind at, and a reminder went out. A
 * date alone is held at the start of its day, belongs to Today on its day, is overdue only
 * once that day has ended, and nothing reminds of it.
 */
import {
  dateOnly,
  describeDueAt,
  dueFieldsToSend,
  overdueAt,
} from "@/features/todos/model/dueDate";
import { firstOverdueHomeTodo } from "@/features/todos/model/homeUrgentTodos";
import { listUrgentReminders, reminderGoesOutAt } from "@/features/todos/model/reminderBadge";
import { clashClusters, findOverlappingReminder, groupBySameTime } from "@/features/todos/model/reminderOverlap";
import { todosForView } from "@/features/todos/model/todoListFilter";
import { buildTodoListRows } from "@/features/todos/model/todoListRows";
import type { Todo } from "@/lib/api";

jest.mock("@/lib/i18n", () => ({
  __esModule: true,
  default: { t: (key: string, options?: { count?: number }) => (options?.count ? `${key}:${options.count}` : key) },
  ensureLocale: jest.fn(),
}));

/** Local wall times: the day math reads the phone's clock. */
const NOV_10 = new Date(2026, 10, 10);
const DAY_END = new Date(2026, 10, 11).getTime();

function todo(partial: Partial<Todo> = {}): Todo {
  return {
    id: "rent", content: "Pay rent", topic: "General", checked: false,
    due_at: NOV_10.toISOString(), due_has_time: false, recurrence_rule: null, sort_order: null,
    chat_id: null, created_at: "2026-11-01T00:00:00Z", updated_at: "2026-11-01T00:00:00Z",
    notify_at: null, ...partial,
  };
}

afterEach(() => jest.useRealTimers());

describe("the day of a date alone", () => {
  it("is overdue once its day has ended, not at its start", () => {
    expect(overdueAt(todo())).toBe(DAY_END);
    expect(overdueAt(todo({ due_has_time: true }))).toBe(NOV_10.getTime());
    expect(overdueAt(todo({ due_at: null }))).toBeNull();
  });

  it("is labelled Today all day, then overdue by days, never 'Today 12:00 AM'", () => {
    jest.useFakeTimers({ now: new Date(2026, 10, 10, 23, 30) });
    expect(describeDueAt(NOV_10.toISOString(), false)).toEqual({ label: "todos.group_today", tone: "today" });
    // With a time at its midnight it would be overdue by now.
    expect(describeDueAt(NOV_10.toISOString())?.tone).toBe("overdue");
    jest.setSystemTime(new Date(2026, 10, 12, 8, 0));
    expect(describeDueAt(NOV_10.toISOString(), false)).toEqual({ label: "todos.overdue_days:2", tone: "overdue" });
  });

  it("stays in Today's group and view on its day, and moves to Overdue after it", () => {
    const late = new Date(2026, 10, 10, 23, 59);
    expect(buildTodoListRows([todo()], late)[0]).toMatchObject({ kind: "heading", section: "today" });
    expect(todosForView([todo()], "today", late)).toHaveLength(1);
    const next = new Date(2026, 10, 11, 0, 1);
    expect(buildTodoListRows([todo()], next)[0]).toMatchObject({ kind: "heading", section: "overdue" });
  });
});

describe("no reminder for a date alone", () => {
  it("counts for the badge and Home only once its day has ended", () => {
    expect(reminderGoesOutAt(todo())).toBe(DAY_END);
    expect(listUrgentReminders([todo()], new Date(2026, 10, 10, 23, 0))).toEqual([]);
    expect(listUrgentReminders([todo()], new Date(DAY_END))).toHaveLength(1);
    expect(firstOverdueHomeTodo([todo()], new Set(), new Date(2026, 10, 10, 12, 0))).toBeUndefined();
    expect(firstOverdueHomeTodo([todo()], new Set(), new Date(DAY_END + 1))?.id).toBe("rent");
  });

  it("shares no time: it overlaps nothing and starts no clash", () => {
    const call = todo({ id: "call", content: "Call", due_has_time: true, due_at: new Date(2026, 10, 10, 0, 5).toISOString() });
    const other = todo({ id: "gym", content: "Gym" });
    expect(findOverlappingReminder([todo()], new Date(2026, 10, 10, 0, 5))).toBeNull();
    expect(clashClusters([todo(), other])).toEqual([]);
    // The day's dates alone share a card; a time at their midnight gets its own.
    expect(groupBySameTime([todo(), other, call]).map((card) => card.map((row) => row.id))).toEqual([["rent", "gym"], ["call"]]);
  });
});

describe("what a save sends for a date alone", () => {
  it("names the picked day with no zone, so the server files it under that day", () => {
    expect(dueFieldsToSend(dateOnly(new Date(2026, 10, 10, 17, 45)))).toEqual({
      due_at: "2026-11-10T00:00:00",
      due_has_time: false,
    });
  });

  it("sends a saved date alone back as saved, and a time as its instant", () => {
    const saved = todo({ due_at: "2026-11-10T05:00:00Z" });
    expect(dueFieldsToSend({ date: new Date(saved.due_at!), hasTime: false }, saved)).toEqual({
      due_at: "2026-11-10T05:00:00Z",
      due_has_time: false,
    });
    const at = new Date(2026, 10, 10, 9, 30);
    expect(dueFieldsToSend({ date: at, hasTime: true }, saved)).toEqual({ due_at: at.toISOString(), due_has_time: true });
    expect(dueFieldsToSend(null)).toEqual({ due_at: null, due_has_time: true });
  });
});
