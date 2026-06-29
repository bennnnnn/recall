import type { HomeUrgentTodo, Todo } from "@/lib/api";
import { describeDueAt } from "@/lib/dueDate";

/** Matches backend `URGENT_TODO_MINUTES` in services/home.py */
export const HOME_URGENT_MINUTES = 60;

/** Open reminders due within the next hour (same rules as GET /home). */
export function listHomeUrgentTodos(todos: Todo[], now = new Date()): HomeUrgentTodo[] {
  const cutoffMs = now.getTime() + HOME_URGENT_MINUTES * 60_000;

  return todos
    .filter((todo) => {
      if (todo.checked || !todo.due_at) return false;
      const dueMs = new Date(todo.due_at).getTime();
      return !Number.isNaN(dueMs) && dueMs <= cutoffMs;
    })
    .sort((a, b) => {
      const aMs = new Date(a.due_at!).getTime();
      const bMs = new Date(b.due_at!).getTime();
      return aMs - bMs;
    })
    .slice(0, 5)
    .map((todo) => {
      const dueMs = new Date(todo.due_at!).getTime();
      return {
        id: todo.id,
        content: todo.content,
        topic: todo.topic,
        due_at: todo.due_at!,
        minutes_until: Math.floor((dueMs - now.getTime()) / 60_000),
      };
    });
}

export function partitionHomeUrgentTodos(urgent: HomeUrgentTodo[]): {
  overdue: HomeUrgentTodo[];
  dueSoon: HomeUrgentTodo[];
} {
  const overdue: HomeUrgentTodo[] = [];
  const dueSoon: HomeUrgentTodo[] = [];
  for (const item of urgent) {
    if (item.minutes_until < 0) overdue.push(item);
    else dueSoon.push(item);
  }
  return { overdue, dueSoon };
}

export function homeUrgentPrompt(todo: HomeUrgentTodo): string {
  if (todo.minutes_until < 0) {
    return `My reminder "${todo.content}" is overdue. What should I do?`;
  }
  return `My reminder "${todo.content}" is due soon. What should I do?`;
}

export function homeUrgentSubtitle(urgent: HomeUrgentTodo[]): string | null {
  if (!urgent.length) return null;
  const { overdue, dueSoon } = partitionHomeUrgentTodos(urgent);
  if (urgent.length > 1) {
    if (overdue.length === urgent.length) {
      return `${urgent.length} reminders overdue.`;
    }
    if (dueSoon.length === urgent.length) {
      return `${urgent.length} reminders in the next hour.`;
    }
    return `${urgent.length} reminders need attention.`;
  }
  const first = urgent[0];
  if (first.minutes_until < 0) return `"${first.content}" is overdue.`;
  const due = describeDueAt(first.due_at);
  if (due) return `Coming up: ${first.content} ${due.label.toLowerCase()}.`;
  return `Coming up: ${first.content}.`;
}
