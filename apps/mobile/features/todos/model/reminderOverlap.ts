import type { Todo } from "@/lib/api";

/** Reminders within this window are treated as overlapping. */
export const REMINDER_OVERLAP_MS = 15 * 60 * 1000;

export function findOverlappingReminder(
  todos: Todo[],
  dueDate: Date,
  options?: { excludeId?: string },
): Todo | null {
  const target = dueDate.getTime();
  if (Number.isNaN(target)) return null;

  for (const todo of todos) {
    if (todo.id === options?.excludeId || todo.checked || !todo.due_at) continue;
    const other = new Date(todo.due_at).getTime();
    if (Number.isNaN(other)) continue;
    if (Math.abs(other - target) < REMINDER_OVERLAP_MS) return todo;
  }
  return null;
}

/** Maps reminder id → the other reminder it overlaps with (dated items only). */
export function buildReminderOverlapNotes(todos: Todo[]): Map<string, string> {
  const open = todos.filter((todo) => !todo.checked && todo.due_at);
  const notes = new Map<string, string>();

  for (let i = 0; i < open.length; i++) {
    for (let j = i + 1; j < open.length; j++) {
      const a = open[i];
      const b = open[j];
      const aTime = new Date(a.due_at as string).getTime();
      const bTime = new Date(b.due_at as string).getTime();
      if (Number.isNaN(aTime) || Number.isNaN(bTime)) continue;
      if (Math.abs(aTime - bTime) >= REMINDER_OVERLAP_MS) continue;
      notes.set(a.id, b.content);
      notes.set(b.id, a.content);
    }
  }

  return notes;
}
