import { useCallback, useMemo } from "react";
import { RefreshControl, Text, View, type TextStyle } from "react-native";
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

function buildTodosTailItems(options: {
  showReminders: boolean;
  isRemindersPage: boolean;
  openReminders: Todo[];
  visibleDone: Todo[];
  focusSection: TodosFocusSection;
  remindersTitle: string;
  doneTitle: string;
}): TodoListItem[] {
  const items: TodoListItem[] = [];
  if (options.showReminders && !options.isRemindersPage && options.openReminders.length > 0) {
    if (!options.focusSection) {
      items.push({
        type: "remindersHeader",
        key: "reminders-h",
        title: options.remindersTitle,
      });
    }
    for (const todo of options.openReminders) {
      items.push({ type: "todoRow", key: todo.id, todo, done: false });
    }
  }
  if (options.visibleDone.length > 0) {
    items.push({
      type: "doneHeader",
      key: "done-h",
      title: options.doneTitle,
    });
    for (const todo of options.visibleDone) {
      items.push({ type: "todoRow", key: todo.id, todo, done: true });
    }
  }
  return items;
}

type Props = {
  showReminders: boolean;
  isRemindersPage: boolean;
  openReminders: Todo[];
  visibleDone: Todo[];
  focusSection: TodosFocusSection;
  busyTodoIds: ReadonlySet<string>;
  highlight?: string;
  overlapNotes: Map<string, string>;
  onToggle: (todo: Todo) => void;
  onDue: (todo: Todo) => void;
  onDeleteItem: (todo: Todo) => void;
  showRemindersEmptyHero: boolean;
  error: boolean;
  listHeader: React.ReactElement;
  refreshing?: boolean;
  onRefresh?: () => void;
};

export function TodosFlashList({
  showReminders,
  isRemindersPage,
  openReminders,
  visibleDone,
  focusSection,
  busyTodoIds,
  highlight,
  overlapNotes,
  onToggle,
  onDue,
  onDeleteItem,
  showRemindersEmptyHero,
  error,
  listHeader,
  refreshing = false,
  onRefresh,
}: Props) {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeTodosStyles(C), [C]);

  const todosData = useMemo<TodoListItem[]>(
    () =>
      buildTodosTailItems({
        showReminders,
        isRemindersPage,
        openReminders,
        visibleDone,
        focusSection,
        remindersTitle: t("todos.section_reminders"),
        doneTitle: `${t("todos.done")} (${visibleDone.length})`,
      }),
    [showReminders, isRemindersPage, openReminders, focusSection, visibleDone, t],
  );

  const renderTodoItem = useCallback(
    ({ item }: { item: TodoListItem }) => (
      <TodosTailItem
        item={item}
        headingStyle={s.sectionHeading}
        busyTodoIds={busyTodoIds}
        highlight={highlight}
        overlapNotes={overlapNotes}
        onToggle={onToggle}
        onDue={onDue}
        onDeleteItem={onDeleteItem}
      />
    ),
    [s, busyTodoIds, highlight, overlapNotes, onToggle, onDue, onDeleteItem],
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
      refreshControl={
        onRefresh ? (
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.primary} />
        ) : undefined
      }
    />
  );
}

type TailProps = Pick<
  Props,
  | "showReminders"
  | "isRemindersPage"
  | "openReminders"
  | "visibleDone"
  | "focusSection"
  | "busyTodoIds"
  | "highlight"
  | "overlapNotes"
  | "onToggle"
  | "onDue"
  | "onDeleteItem"
>;

/** Reminder + done rows for when Lists owns the page scroller. */
export function TodosRemindersTail({
  showReminders,
  isRemindersPage,
  openReminders,
  visibleDone,
  focusSection,
  busyTodoIds,
  highlight,
  overlapNotes,
  onToggle,
  onDue,
  onDeleteItem,
}: TailProps) {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeTodosStyles(C), [C]);

  const items = useMemo<TodoListItem[]>(
    () =>
      buildTodosTailItems({
        showReminders,
        isRemindersPage,
        openReminders,
        visibleDone,
        focusSection,
        remindersTitle: t("todos.section_reminders"),
        doneTitle: `${t("todos.done")} (${visibleDone.length})`,
      }),
    [showReminders, isRemindersPage, openReminders, focusSection, visibleDone, t],
  );

  if (items.length === 0) return null;

  return (
    <View>
      {items.map((item) => (
        <TodosTailItem
          key={item.key}
          item={item}
          headingStyle={s.sectionHeading}
          busyTodoIds={busyTodoIds}
          highlight={highlight}
          overlapNotes={overlapNotes}
          onToggle={onToggle}
          onDue={onDue}
          onDeleteItem={onDeleteItem}
        />
      ))}
    </View>
  );
}

function TodosTailItem({
  item,
  headingStyle,
  busyTodoIds,
  highlight,
  overlapNotes,
  onToggle,
  onDue,
  onDeleteItem,
}: {
  item: TodoListItem;
  headingStyle: TextStyle;
} & Pick<
  TailProps,
  "busyTodoIds" | "highlight" | "overlapNotes" | "onToggle" | "onDue" | "onDeleteItem"
>) {
  if (item.type === "remindersHeader" || item.type === "doneHeader") {
    return <Text style={headingStyle}>{item.title}</Text>;
  }
  const todo = item.todo;
  return (
    <TodoRow
      todo={todo}
      variant={item.done ? "done" : "open"}
      highlighted={!item.done && highlight === todo.id}
      overlapWith={item.done ? undefined : overlapNotes.get(todo.id)}
      busy={busyTodoIds.has(todo.id)}
      onToggle={onToggle}
      onDue={item.done && !isReminder(todo) ? undefined : onDue}
      onDelete={onDeleteItem}
    />
  );
}
