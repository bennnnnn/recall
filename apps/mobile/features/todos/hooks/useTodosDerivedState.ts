import { useMemo } from "react";

import { sortOpen } from "@/features/todos/components/todoHelpers";
import type { Todo } from "@/lib/api";

export function useTodosDerivedState(todos: Todo[]) {
  const openTodos = useMemo(
    () => sortOpen(todos.filter((item) => !item.checked)),
    [todos],
  );
  const completedTodos = useMemo(
    () =>
      [...todos]
        .filter((item) => item.checked)
        .sort((a, b) => b.created_at.localeCompare(a.created_at)),
    [todos],
  );
  const isEmpty = openTodos.length === 0 && completedTodos.length === 0;

  return {
    openTodos,
    completedTodos,
    showTodosEmptyHero: isEmpty,
  };
}
