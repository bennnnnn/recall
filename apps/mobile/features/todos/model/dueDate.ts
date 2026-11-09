import i18n from "@/lib/i18n";
import type { Todo } from "@/lib/api";
import { formatDate } from "@/lib/datetime/format";
import { localDayKey } from "@/lib/datetime/dayKey";

type DueTone = "overdue" | "today" | "soon" | "later";

/**
 * A to-do's due date, and whether it has a time. A date alone (`due_has_time` false) has
 * no time and no reminder, and is overdue once its day has ended; its `date` is the start
 * of that day. Picking a date used to write a time with it (9:00, or the next hour), so a
 * date alone came with a "Remind at" and a reminder.
 */
export type TodoDue = { date: Date; hasTime: boolean };

type DueFields = Pick<Todo, "due_at" | "due_has_time" | "due_date">;
type SentDue = Required<Pick<Todo, "due_at" | "due_has_time">>;

const DAY = /^(\d{4})-(\d{2})-(\d{2})$/;

export function describeDueAt(iso: string | null | undefined, hasTime = true): {
  label: string;
  tone: DueTone;
} | null {
  if (!iso) return null;
  const due = new Date(iso);
  if (Number.isNaN(due.getTime())) return null;

  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startOfDue = new Date(due.getFullYear(), due.getMonth(), due.getDate());
  const dayDiff = Math.round(
    (startOfDue.getTime() - startOfToday.getTime()) / (24 * 60 * 60 * 1000),
  );

  // A date alone is overdue only once its day has ended, and has no time to name.
  if (hasTime ? due.getTime() < now.getTime() : dayDiff < 0) {
    if (dayDiff === 0) return { label: i18n.t("todos.overdue_today"), tone: "overdue" };
    const days = Math.max(1, Math.abs(dayDiff));
    return { label: i18n.t("todos.overdue_days", { count: days }), tone: "overdue" };
  }
  if (dayDiff === 0) {
    return {
      label: hasTime
        ? i18n.t("todos.due_today_time", { time: formatDate(due, "time") })
        : i18n.t("todos.group_today"),
      tone: "today",
    };
  }
  if (dayDiff === 1) return { label: i18n.t("todos.group_tomorrow"), tone: "soon" };
  if (dayDiff <= 7) {
    return {
      label: formatDate(due, "weekdayDate"),
      tone: "soon",
    };
  }
  return {
    label: formatDate(due, "monthDayYear"),
    tone: "later",
  };
}

/** Keep the clock time and take the calendar day, including the year. */
export function withCalendarDate(current: Date, picked: Date): Date {
  const next = new Date(current);
  next.setFullYear(picked.getFullYear(), picked.getMonth(), picked.getDate());
  return next;
}

/** A new to-do's suggested time: 9:00 today, or the next whole hour once it is past nine. */
export function defaultDueDate(): Date {
  const now = new Date();
  const nineToday = new Date(now);
  nineToday.setHours(9, 0, 0, 0);
  if (nineToday.getTime() > now.getTime()) return nineToday;
  const nextHour = new Date(now);
  nextHour.setMinutes(0, 0, 0);
  nextHour.setHours(nextHour.getHours() + 1);
  return nextHour;
}

/** `date`'s day alone, held at its start on the phone's clock. */
export function dateOnly(date: Date): TodoDue {
  return { date: new Date(date.getFullYear(), date.getMonth(), date.getDate()), hasTime: false };
}

/**
 * A saved to-do's due date, as the list, the editor and the overdue rule read it; null when
 * it has none. A date alone is its `due_date` at the start of that day on the phone's clock:
 * the server holds it at the start of the day in the profile's zone, which read in a zone
 * to the west fell on the day before.
 */
export function dueOfTodo(todo: DueFields): TodoDue | null {
  if (!todo.due_at) return null;
  const day = todo.due_has_time === false ? DAY.exec(todo.due_date ?? "") : null;
  if (day) return { date: new Date(Number(day[1]), Number(day[2]) - 1, Number(day[3])), hasTime: false };
  const date = new Date(todo.due_at);
  return Number.isFinite(date.getTime()) ? { date, hasTime: todo.due_has_time !== false } : null;
}

/** The same due date, with a time or without one. */
export function sameDue(a: TodoDue | null, b: TodoDue | null): boolean {
  if (!a || !b) return a === b;
  return a.date.getTime() === b.date.getTime() && a.hasTime === b.hasTime;
}

/**
 * When a to-do is overdue, as epoch ms: its time, or for a date alone the end of its day
 * (until then it is Today's). Null when it has no date.
 */
export function overdueAt(todo: DueFields): number | null {
  const due = dueOfTodo(todo);
  if (!due) return null;
  const day = due.date;
  return due.hasTime ? day.getTime() : new Date(day.getFullYear(), day.getMonth(), day.getDate() + 1).getTime();
}

/** A date alone: no time, and nothing reminds of it. */
export function isDateOnly(todo: DueFields): boolean {
  return Boolean(todo.due_at) && todo.due_has_time === false;
}

/** The due fields the list holds for `due` until the server answers. */
export function dueFields(due: TodoDue | null): Required<DueFields> {
  return {
    due_at: due ? due.date.toISOString() : null,
    due_has_time: due?.hasTime ?? true,
    due_date: due && !due.hasTime ? localDayKey(due.date) : null,
  };
}

/**
 * The due fields a save sends. A date alone goes as its day at 00:00 with no zone: the
 * server files it under that day on the user's clock, even before it holds the phone's zone
 * (a new account, just after a flight). One still as `saved` has it goes back as saved.
 */
export function dueFieldsToSend(due: TodoDue | null, saved?: Todo): SentDue {
  if (!due || due.hasTime) return { due_at: due ? due.date.toISOString() : null, due_has_time: true };
  if (saved?.due_at && sameDue(dueOfTodo(saved), due)) return { due_at: saved.due_at, due_has_time: false };
  return { due_at: `${localDayKey(due.date)}T00:00:00`, due_has_time: false };
}
