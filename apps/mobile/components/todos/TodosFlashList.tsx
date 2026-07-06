import { useCallback, useMemo } from "react";
import { Text } from "react-native";
import { FlashList } from "@shopify/flash-list";
import { useTranslation } from "react-i18next";

import { isReminder } from "@/components/todos/todoHelpers";
import { TodoRow } from "@/components/todos/TodoRow";
import { makeTodosStyles } from "@/components/todos/todosStyles";
import type { TodosFocusSection } from "@/hooks/useTodosDerivedState";
import type { Todo } from "@/lib/api";
import { useTheme } from "@/lib/theme";

type TodoListItem =
  | { type: "remindersHeader"; key: string; title: string }
  | { type: "doneHeader"; key: string; title: string }
  | { type: "todoRow"; key: string; todo: Todo; done: boolean };

type Props = {
  showReminders: boolean;
  isRemindersPage: boolean;
  openReminders: Todo[];
  visibleDone: Todo[];
  focusSection: TodosFocusSection;
  togglingId: string | null;
  highlight?: string;
  overlapNotes: Map<string, string>;
  onToggle: (todo: Todo) => void;
  onDue: (todo: Todo) => void;
  onDeleteItem: (todo: Todo) => void;
  showRemindersEmptyHero: boolean;
  error: boolean;
  listHeader: React.ReactElement;
};

export function TodosFlashList({
  showReminders,
  isRemindersPage,
  openReminders,
  visibleDone,
  focusSection,
  togglingId,
  highlight,
  overlapNotes,
  onToggle,
  onDue,
  onDeleteItem,
  showRemindersEmptyHero,
  error,
  listHeader,
}: Props) {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeTodosStyles(C), [C]);

  const todosData = useMemo<TodoListItem[]>(() => {
    const items: TodoListItem[] = [];
    if (showReminders && !isRemindersPage && openReminders.length > 0) {
      if (!focusSection) {
        items.push({
          type: "remindersHeader",
          key: "reminders-h",
          title: t("todos.section_reminders"),
        });
      }
      for (const todo of openReminders) {
        items.push({ type: "todoRow", key: todo.id, todo, done: false });
      }
    }
    if (visibleDone.length > 0) {
      items.push({
        type: "doneHeader",
        key: "done-h",
        title: `${t("todos.done")} (${visibleDone.length})`,
      });
      for (const todo of visibleDone) {
        items.push({ type: "todoRow", key: todo.id, todo, done: true });
      }
    }
    return items;
  }, [showReminders, isRemindersPage, openReminders, focusSection, visibleDone, t]);

  const renderTodoItem = useCallback(
    ({ item }: { item: TodoListItem }) => {
      if (item.type === "remindersHeader" || item.type === "doneHeader") {
        return <Text style={s.sectionHeading}>{item.title}</Text>;
      }
      const todo = item.todo;
      if (item.done) {
        return (
          <TodoRow
            key={todo.id}
            todo={todo}
            variant="done"
            busy={togglingId === todo.id}
            onToggle={() => onToggle(todo)}
            onDue={isReminder(todo) ? () => onDue(todo) : undefined}
            onDelete={() => onDeleteItem(todo)}
          />
        );
      }
      return (
        <TodoRow
          key={todo.id}
          todo={todo}
          variant="open"
          highlighted={highlight === todo.id}
          overlapWith={overlapNotes.get(todo.id)}
          busy={togglingId === todo.id}
          onToggle={() => onToggle(todo)}
          onDue={() => onDue(todo)}
          onDelete={() => onDeleteItem(todo)}
        />
      );
    },
    [s, togglingId, highlight, overlapNotes, onToggle, onDue, onDeleteItem],
  );

  return (
    <FlashList
      style={s.list}
      data={todosData}
      renderItem={renderTodoItem}
      keyExtractor={(item) => item.key}
      getItemType={(item) => item.type}
      contentContainerStyle={showRemindersEmptyHero && !error ? s.listEmpty : undefined}
      keyboardShouldPersistTaps="handled"
      ListHeaderComponent={listHeader}
    />
  );
}
