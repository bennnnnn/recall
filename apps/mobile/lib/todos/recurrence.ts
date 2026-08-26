export const RECURRENCE_RULES = ["daily", "weekdays", "weekly", "monthly"] as const;
export type RecurrenceRule = (typeof RECURRENCE_RULES)[number];

export function isRecurrenceRule(value: unknown): value is RecurrenceRule {
  return (
    typeof value === "string" &&
    (RECURRENCE_RULES as readonly string[]).includes(value)
  );
}

function addMonth(due: Date): Date {
  const next = new Date(due);
  const day = next.getDate();
  next.setMonth(next.getMonth() + 1);
  if (next.getDate() < day) {
    next.setDate(0);
  }
  return next;
}

function stepLocal(due: Date, rule: RecurrenceRule): Date {
  const next = new Date(due);
  if (rule === "daily") {
    next.setDate(next.getDate() + 1);
    return next;
  }
  if (rule === "weekly") {
    next.setDate(next.getDate() + 7);
    return next;
  }
  if (rule === "monthly") {
    return addMonth(due);
  }
  do {
    next.setDate(next.getDate() + 1);
  } while (next.getDay() === 0 || next.getDay() === 6);
  return next;
}

export function snapFirstDue(due: Date, rule: RecurrenceRule | null): Date {
  if (rule !== "weekdays") return due;
  const next = new Date(due);
  while (next.getDay() === 0 || next.getDay() === 6) {
    next.setDate(next.getDate() + 1);
  }
  return next;
}

export function nextRecurringDue(
  due: Date,
  rule: RecurrenceRule,
  now: Date = new Date(),
): Date {
  let next = new Date(due);
  for (let i = 0; i < 400 && next.getTime() <= now.getTime(); i += 1) {
    next = stepLocal(next, rule);
  }
  return next;
}

export function applyRecurrenceAdvances(
  todos: { due_at: string | null; recurrence_rule?: RecurrenceRule | null; checked: boolean }[],
  now: Date = new Date(),
): { todos: typeof todos; changedIndexes: number[] } {
  const changedIndexes: number[] = [];
  const next = todos.map((todo, index) => {
    if (
      !needsRecurrenceAdvance(todo.due_at, todo.recurrence_rule, todo.checked, now)
    ) {
      return todo;
    }
    const rule = todo.recurrence_rule;
    if (!todo.due_at || !rule) return todo;
    changedIndexes.push(index);
    return {
      ...todo,
      due_at: nextRecurringDue(new Date(todo.due_at), rule, now).toISOString(),
    };
  });
  return { todos: next, changedIndexes };
}

export function needsRecurrenceAdvance(
  dueAt: string | null | undefined,
  rule: RecurrenceRule | null | undefined,
  checked: boolean,
  now: Date = new Date(),
): boolean {
  if (checked || !dueAt || !rule) return false;
  return new Date(dueAt).getTime() <= now.getTime();
}
