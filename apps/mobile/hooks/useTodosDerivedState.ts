import { useMemo } from "react";

import { isReminder, sortOpen } from "@/components/todos/todoHelpers";
import type { ListGroup } from "@/lib/listGroups";
import type { Todo } from "@/lib/api";

export type TodosFocusSection = "list" | "reminders" | null;

export function useTodosDerivedState(
  todos: Todo[],
  focusSection: TodosFocusSection,
  listGroups: ListGroup[],
  hasNamedGroups: boolean,
) {
  const openReminders = useMemo(
    () => sortOpen(todos.filter((item) => isReminder(item) && !item.checked)),
    [todos],
  );
  const doneItems = useMemo(
    () =>
      [...todos]
        .filter((item) => item.checked)
        .sort((a, b) => b.created_at.localeCompare(a.created_at)),
    [todos],
  );
  const doneReminders = useMemo(
    () => doneItems.filter((item) => isReminder(item)),
    [doneItems],
  );
  const visibleDone = useMemo(() => {
    if (focusSection === "list" || focusSection === "reminders") return [];
    return doneReminders;
  }, [doneReminders, focusSection]);
  const hasListItems = todos.some((item) => !isReminder(item));
  const isEmpty = useMemo(() => {
    if (focusSection === "list") {
      return listGroups.length === 0;
    }
    if (focusSection === "reminders") {
      return openReminders.length === 0 && doneReminders.length === 0;
    }
    return (
      openReminders.length === 0 && !hasListItems && doneReminders.length === 0 && !hasNamedGroups
    );
  }, [
    doneReminders.length,
    focusSection,
    hasListItems,
    hasNamedGroups,
    listGroups.length,
    openReminders.length,
  ]);
  const isRemindersPage = focusSection === "reminders";
  // Empty hero for Lists page, combined empty, AND Reminders page with zero reminders.
  const showRemindersEmptyHero = isEmpty;

  return {
    openReminders,
    visibleDone,
    isEmpty,
    isRemindersPage,
    showRemindersEmptyHero,
  };
}
