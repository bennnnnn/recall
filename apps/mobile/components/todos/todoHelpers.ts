import type { Todo } from "@/lib/api";
import { localDateKey } from "@/lib/reminderCalendar";

export function sortOpen(items: Todo[]): Todo[] {
  return [...items].sort((a, b) => {
    if (a.checked !== b.checked) return Number(a.checked) - Number(b.checked);
    const aDue = a.due_at ? new Date(a.due_at).getTime() : Number.POSITIVE_INFINITY;
    const bDue = b.due_at ? new Date(b.due_at).getTime() : Number.POSITIVE_INFINITY;
    if (aDue !== bDue) return aDue - bDue;
    return b.created_at.localeCompare(a.created_at);
  });
}

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

export function dayKeyForDue(dueDate: Date, dueIso?: string | null): string {
  if (dueIso && !Number.isNaN(new Date(dueIso).getTime())) {
    return localDateKey(new Date(dueIso));
  }
  return localDateKey(dueDate);
}

export function isReminder(todo: Todo): boolean {
  return Boolean(todo.due_at);
}
