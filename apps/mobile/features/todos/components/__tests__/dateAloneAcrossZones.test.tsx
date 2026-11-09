/**
 * @jest-environment ./jest.timeZoneEnvironment.js
 */
/**
 * A date alone is held at the start of its day in the profile's zone. Read in the phone's
 * zone, that instant falls on the day before for a phone to the west (a flight not yet
 * reported, or a zone the server refused), so the list, its heading, Today, the overdue rule
 * and the editor read the day the server sends (`due_date`) instead.
 */
import { render } from "@testing-library/react-native";

import { TodoDateFields } from "@/features/todos/components/TodoDateFields";
import { dueFields, dueOfTodo, overdueAt } from "@/features/todos/model/dueDate";
import { todosForView } from "@/features/todos/model/todoListFilter";
import { buildTodoListRows } from "@/features/todos/model/todoListRows";
import type { Todo } from "@/lib/api";
import { formatDate, refreshPhoneClock } from "@/lib/datetime/format";

declare const setTestTimeZone: (zone: string) => void;

jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key, i18n: { language: "en" } }),
  initReactI18next: { type: "3rdParty", init: () => undefined },
}));
jest.mock("@/features/todos/model/todoReminders", () => ({
  ensureNotificationPermission: jest.fn(async () => true),
}));

/** The 10th as a New York profile holds it: 21:00 on the 9th in Los Angeles. */
const RENT = {
  id: "rent", content: "Pay rent", topic: "General", checked: false, due_at: "2026-11-10T05:00:00Z",
  due_has_time: false, due_date: "2026-11-10", recurrence_rule: null, sort_order: null, chat_id: null,
  created_at: "2026-11-01T00:00:00Z", updated_at: "2026-11-01T00:00:00Z", notify_at: null,
} as Todo;
const noop = () => undefined;

beforeEach(() => {
  setTestTimeZone("America/Los_Angeles");
  refreshPhoneClock();
});

it("lists, heads and edits it on its own day on a phone west of the profile", async () => {
  const ninthNoon = new Date(2026, 10, 9, 12, 0);
  expect(buildTodoListRows([RENT], ninthNoon)[0]).toMatchObject({ kind: "heading", section: "tomorrow" });
  expect(todosForView([RENT], "today", ninthNoon)).toEqual([]);
  // Overdue once the 10th has ended on the phone's clock, not at 21:00 on the 9th.
  expect(overdueAt(RENT)).toBe(new Date(2026, 10, 11).getTime());

  const editor = await render(
    <TodoDateFields review due={dueOfTodo(RENT)} onDueChange={noop} repeat={null}
      onRepeatChange={noop} todos={[]} onOpen={noop} />,
  );
  expect(editor.getByText(formatDate(new Date(2026, 10, 10), "monthDayYear"))).toBeTruthy();
});

it("holds a date alone picked on the phone with its day until the server answers", () => {
  expect(dueFields({ date: new Date(2026, 10, 10), hasTime: false })).toMatchObject({
    due_has_time: false,
    due_date: "2026-11-10",
  });
  expect(dueFields({ date: new Date(2026, 10, 10, 9), hasTime: true }).due_date).toBeNull();
});
