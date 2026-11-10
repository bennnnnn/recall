/**
 * @jest-environment ./jest.timeZoneEnvironment.js
 */
/**
 * The editor's "Remind at" shows the server's instant (the lead time, after quiet hours),
 * the one push and the phone's alert fire at: the saved to-do's notify_at, or for a due
 * time the editor has not saved, the server's preview of it, one request once it settles.
 * With quiet hours 22:00-07:00, a to-do due at 23:30 showed 23:20 (due - lead) here while
 * push waited until 07:00.
 */
import { createRef } from "react";
import { act, fireEvent, render } from "@testing-library/react-native";

import { TodoDateFields } from "@/features/todos/components/TodoDateFields";
import { TodoEditorSheet, type TodoEditorHandle } from "@/features/todos/components/TodoEditorSheet";
import { useRemindAt } from "@/features/todos/hooks/useRemindAt";
import { api, type Todo, type User } from "@/lib/api";
import { formatDate, refreshPhoneClock } from "@/lib/datetime/format";

declare const setTestTimeZone: (zone: string) => void;

jest.mock("@/features/todos/model/todoReminders", () => ({
  ensureNotificationPermission: jest.fn(async () => true),
}));
jest.mock("@/lib/api", () => ({ api: { previewReminder: jest.fn() } }));
let mockAuth: { token: string; user: User } = {
  token: "a",
  user: { id: "u1", reminder_lead_minutes: 10, quiet_hours_enabled: true, quiet_hours_start_minute: 1320,
    quiet_hours_end_minute: 420, timezone: "UTC" } as User,
};
jest.mock("@/contexts/AuthContext", () => ({ useAuthOptional: () => mockAuth }));

const ZONES = ["UTC", "Asia/Kathmandu", "Pacific/Kiritimati", "America/St_Johns"];
const noop = () => undefined;
const time = (date: Date) => formatDate(date, "time");
/** A reminder on another day than the due date names its day. */
const dayTime = (date: Date) => formatDate(date, "weekdayTime");
const previews = () => jest.mocked(api.previewReminder).mock.calls.map(([, dueAt]) => dueAt);

function savedTodo(due: Date, notifyAt: Date | null): Todo {
  return {
    id: "t1", content: "Call Sam", topic: "Reminders", checked: false, due_at: due.toISOString(),
    recurrence_rule: null, sort_order: null, chat_id: null, created_at: "2026-10-01T00:00:00Z",
    updated_at: "2026-10-01T00:00:00Z", notify_at: notifyAt?.toISOString() ?? null,
  };
}

/** The detail page's date fields with the date on screen, as TodoEditorSheet wires them. */
function Fields({ due, saved }: { due: Date | null; saved?: Todo | null }) {
  const remindAt = useRemindAt({ dueDate: due, repeat: null, saved, enabled: true });
  return (
    <TodoDateFields review due={due && { date: due, hasTime: true }} onDueChange={noop} repeat={null} onRepeatChange={noop}
      todos={[]} remindAt={remindAt} leadMinutes={mockAuth.user.reminder_lead_minutes} onOpen={noop} />
  );
}

const remindAtLabel = (view: Awaited<ReturnType<typeof render>>) =>
  view.queryByLabelText(/^todos\.remind_at,/)?.props.accessibilityLabel as string | undefined;
const advance = (ms: number) => act(async () => { await jest.advanceTimersByTimeAsync(ms); });

beforeEach(() => {
  jest.clearAllMocks();
  jest.useFakeTimers({ now: new Date("2026-10-25T12:00:00Z") });
  mockAuth = { ...mockAuth, user: { ...mockAuth.user, reminder_lead_minutes: 10 } };
});
afterEach(() => jest.useRealTimers());

describe.each(ZONES)("in %s, quiet hours 22:00-07:00", (zone) => {
  beforeEach(() => {
    setTestTimeZone(zone);
    refreshPhoneClock();
  });

  it("a to-do due 23:30 shows Remind at 07:00 the next day, not 23:20, with no request", async () => {
    // Local wall times: the process is in `zone`.
    const due = new Date(2026, 10, 2, 23, 30);
    const notifyAt = new Date(2026, 10, 3, 7, 0);
    const view = await render(<Fields due={due} saved={savedTodo(due, notifyAt)} />);
    // "Tue 7:00 AM": a bare "7:00 AM" beside a 23:30 due time reads as that morning.
    expect(dayTime(notifyAt)).not.toBe(time(notifyAt));
    expect(view.getByText(dayTime(notifyAt))).toBeTruthy();
    expect(view.queryByText(time(new Date(due.getTime() - 10 * 60_000)))).toBeNull();
    expect(remindAtLabel(view)).toBe(`todos.remind_at, ${dayTime(notifyAt)}, settings.reminder_lead_value`);
    expect(previews()).toEqual([]);
  });

  it("a lead that crosses midnight names the evening before; the same day shows the time alone", async () => {
    const due = new Date(2026, 10, 3, 0, 5);
    const notifyAt = new Date(2026, 10, 2, 23, 55);
    const view = await render(<Fields due={due} saved={savedTodo(due, notifyAt)} />);
    expect(view.getByText(dayTime(notifyAt))).toBeTruthy();

    const noon = new Date(2026, 10, 3, 12, 0);
    const before = new Date(2026, 10, 3, 11, 50);
    await view.rerender(<Fields due={noon} saved={savedTodo(noon, before)} />);
    expect(view.getByText(time(before))).toBeTruthy();
    expect(view.queryByText(dayTime(before))).toBeNull();
  });

  it("a due time not yet saved: one request once it settles, then the server's answer", async () => {
    const savedDue = new Date(2026, 10, 2, 9, 0);
    const saved = savedTodo(savedDue, new Date(2026, 10, 2, 8, 50));
    const night = new Date(2026, 10, 2, 23, 30);
    const morning = new Date(2026, 10, 3, 7, 0);
    jest.mocked(api.previewReminder).mockImplementation(async (_token, dueAt) => ({
      notify_at: dueAt === night.toISOString() ? morning.toISOString() : null,
    }));
    const view = await render(<Fields due={savedDue} saved={saved} />);
    expect(view.getByText(time(new Date(2026, 10, 2, 8, 50)))).toBeTruthy();

    // The time picker's OK: the row waits for the server ("—"), never shows due - lead.
    await view.rerender(<Fields due={night} saved={saved} />);
    expect(remindAtLabel(view)).toBe("todos.remind_at, settings.reminder_lead_value");
    expect(view.getByText("—")).toBeTruthy();
    await advance(299);
    expect(previews()).toEqual([]);
    await advance(1);
    expect(previews()).toEqual([night.toISOString()]);
    expect(view.getByText(dayTime(morning))).toBeTruthy();
    expect(view.queryByText(time(new Date(night.getTime() - 10 * 60_000)))).toBeNull();

    // Back to the saved time: its notify_at, no request.
    await view.rerender(<Fields due={savedDue} saved={saved} />);
    await advance(1000);
    expect(view.getByText(time(new Date(2026, 10, 2, 8, 50)))).toBeTruthy();
    expect(previews()).toHaveLength(1);
  });
});

it("asks once for several quick changes, and again when the lead time changes", async () => {
  setTestTimeZone("Asia/Kathmandu");
  refreshPhoneClock();
  jest.mocked(api.previewReminder).mockImplementation(async (_token, dueAt) => ({
    notify_at: new Date(Date.parse(dueAt) - mockAuth.user.reminder_lead_minutes * 60_000).toISOString(),
  }));
  const view = await render(<Fields due={null} />);
  for (const hour of [20, 21, 21]) {
    await view.rerender(<Fields due={new Date(2026, 10, 2, hour, 0)} />);
    await advance(100);
  }
  await view.rerender(<Fields due={new Date(2026, 10, 2, 21, 30)} />);
  await advance(300);
  expect(previews()).toEqual([new Date(2026, 10, 2, 21, 30).toISOString()]);
  expect(view.getByText(time(new Date(2026, 10, 2, 21, 20)))).toBeTruthy();

  // The Remind at menu saved a 30-minute lead: the server works out the new instant.
  mockAuth = { ...mockAuth, user: { ...mockAuth.user, reminder_lead_minutes: 30 } };
  await view.rerender(<Fields due={new Date(2026, 10, 2, 21, 30)} />);
  await advance(300);
  expect(previews()).toHaveLength(2);
  expect(view.getByText(time(new Date(2026, 10, 2, 21, 0)))).toBeTruthy();
});

it("shows no reminder time when the server sends none (more than 48 hours past due)", async () => {
  setTestTimeZone("Pacific/Kiritimati");
  refreshPhoneClock();
  const longAgo = new Date(2026, 9, 20, 9, 0);
  const view = await render(<Fields due={longAgo} saved={savedTodo(longAgo, null)} />);
  expect(remindAtLabel(view)).toBeUndefined();

  jest.mocked(api.previewReminder).mockResolvedValue({ notify_at: null });
  await view.rerender(<Fields due={new Date(2026, 9, 19, 9, 0)} saved={savedTodo(longAgo, null)} />);
  await advance(300);
  expect(previews()).toHaveLength(1);
  expect(remindAtLabel(view)).toBeUndefined();
});

it("the detail page shows the list's notify_at for the to-do, and follows it when it moves", async () => {
  setTestTimeZone("Asia/Kathmandu");
  refreshPhoneClock();
  const due = new Date(2026, 10, 2, 23, 30);
  const edited = savedTodo(due, new Date(2026, 10, 2, 23, 20));
  const page = (live: Todo) => (
    <TodoEditorSheet page visible saving={false} todos={[live]} editTodo={edited} savedTodo={live}
      leadMinutes={10} onClose={noop} onSave={noop} />
  );
  const view = await render(page(edited));
  expect(view.getByText(time(new Date(2026, 10, 2, 23, 20)))).toBeTruthy();

  // Quiet hours turned on, or the zone reported: the list read again has the new instant.
  await view.rerender(page(savedTodo(due, new Date(2026, 10, 3, 7, 0))));
  expect(view.getByText(dayTime(new Date(2026, 10, 3, 7, 0)))).toBeTruthy();
  await advance(1000);
  expect(previews()).toEqual([]);
});

describe("a date alone on the detail page", () => {
  const page = (shown: Todo) => (
    <TodoEditorSheet page visible saving={false} todos={[shown]} editTodo={shown} savedTodo={shown}
      leadMinutes={10} onClose={noop} onSave={noop} />
  );

  it("shows no time and no Remind at, and asks the server nothing", async () => {
    const day = new Date(2026, 10, 2);
    const rent = { ...savedTodo(day, null), due_has_time: false };
    const view = await render(page(rent));
    expect(view.getByText("—")).toBeTruthy();
    expect(remindAtLabel(view)).toBeUndefined();
    expect(view.queryByLabelText("todos.remove_time")).toBeNull();
    await advance(1000);
    expect(previews()).toEqual([]);
  });

  it("is what taking the time off leaves: the Remind at row goes with the time", async () => {
    const due = new Date(2026, 10, 2, 9, 0);
    const view = await render(page(savedTodo(due, new Date(2026, 10, 2, 8, 50))));
    expect(remindAtLabel(view)).toBeDefined();
    await fireEvent.press(view.getByLabelText("todos.remove_time"));
    expect(remindAtLabel(view)).toBeUndefined();
    expect(view.getByText("—")).toBeTruthy();
    await advance(1000);
    expect(previews()).toEqual([]);
  });
});

describe("taking the date off on the detail page", () => {
  it("leaves an undated to-do: no time, Remind at or repeat, and leaving saves it so", async () => {
    const due = new Date(2026, 10, 2, 9, 0);
    const shown: Todo = { ...savedTodo(due, new Date(2026, 10, 2, 8, 50)), recurrence_rule: "weekly" };
    const onSave = jest.fn();
    const ref = createRef<TodoEditorHandle>();
    const view = await render(
      <TodoEditorSheet ref={ref} page visible saving={false} todos={[shown]} editTodo={shown} savedTodo={shown}
        leadMinutes={10} onClose={noop} onSave={onSave} />,
    );
    expect(remindAtLabel(view)).toBeDefined();
    await fireEvent.press(view.getByLabelText("todos.remove_date"));
    expect(view.getByLabelText("todos.add_date")).toBeTruthy();
    expect(view.queryByLabelText("todos.remove_date")).toBeNull();
    expect(view.queryByLabelText("todos.remove_time")).toBeNull();
    expect(remindAtLabel(view)).toBeUndefined();
    await act(async () => ref.current?.leave());
    expect(onSave).toHaveBeenCalledWith("Call Sam", null, null, "Reminders");
  });

  it("offers no remove button on an undated to-do", async () => {
    const undated: Todo = { ...savedTodo(new Date(2026, 10, 2), null), due_at: null };
    const view = await render(
      <TodoEditorSheet page visible saving={false} todos={[undated]} editTodo={undated} savedTodo={undated}
        leadMinutes={10} onClose={noop} onSave={noop} />,
    );
    expect(view.getByLabelText("todos.add_date")).toBeTruthy();
    expect(view.queryByLabelText("todos.remove_date")).toBeNull();
  });
});
