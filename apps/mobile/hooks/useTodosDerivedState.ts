import { useMemo } from "react";

import { isReminder, sortOpen } from "@/components/todos/todoHelpers";
import type { Todo } from "@/lib/api";

export function useTodosDerivedState(todos: Todo[]) {
  const openReminders = useMemo(
    () => sortOpen(todos.filter((item) => isReminder(item) && !item.checked)),
    [todos],
  );
  const doneReminders = useMemo(
    () =>
      [...todos]
        .filter((item) => isReminder(item) && item.checked)
        .sort((a, b) => b.created_at.localeCompare(a.created_at)),
    [todos],
  );
  const isEmpty =
    openReminders.length === 0 && doneReminders.length === 0;

  return {
    openReminders,
    showRemindersEmptyHero: isEmpty,
  };
}
