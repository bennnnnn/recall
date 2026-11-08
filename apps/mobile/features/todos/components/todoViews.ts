import type { TodoView } from "@/features/todos/model/todoListFilter";
import type { IconName } from "@/ui/icons/names";

type TodoViewCopy = {
  /** Its row in the ⋯ menu, and the line under the To-do title while it shows. */
  label: string;
  /** The list when this view holds nothing while other to-dos exist: icon + title only. */
  emptyTitle: string;
  emptyIcon: IconName;
};

/** Each list view's name and empty state, in the ⋯ menu's order. */
export const TODO_VIEWS: readonly (TodoViewCopy & { id: TodoView })[] = [
  { id: "all", label: "todos.menu_all", emptyTitle: "todos.empty_title", emptyIcon: "check-circle" },
  { id: "open", label: "todos.menu_open", emptyTitle: "todos.view_empty_open", emptyIcon: "check-circle" },
  { id: "completed", label: "todos.menu_completed", emptyTitle: "todos.view_empty_completed", emptyIcon: "circle" },
  { id: "today", label: "todos.menu_today", emptyTitle: "todos.view_empty_today", emptyIcon: "calendar" },
];

export function todoViewCopy(view: TodoView): TodoViewCopy {
  return TODO_VIEWS.find((item) => item.id === view) ?? TODO_VIEWS[0]!;
}
