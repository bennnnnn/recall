import { useMemo, type ReactElement } from "react";
import { RefreshControl, Text, View } from "react-native";
import { FlashList } from "@shopify/flash-list";
import { useTranslation } from "react-i18next";

import { TodoRow } from "@/features/todos/components/TodoRow";
import { makeTodosStyles } from "@/features/todos/components/todosStyles";
import type { Todo } from "@/lib/api";
import { todoListRowKey, type TodoListRow } from "@/features/todos/model/todoListRows";
import { useTheme } from "@/lib/theme";

type Props = {
  rows: TodoListRow[];
  showEmpty: boolean;
  error: boolean;
  listHeader: ReactElement;
  refreshing?: boolean;
  onRefresh?: () => void;
  highlight?: string;
  overlapNotes: Map<string, string>;
  busyTodoIds: ReadonlySet<string>;
  onToggle: (todo: Todo) => void;
  onDue: (todo: Todo) => void;
  onDeleteItem: (todo: Todo) => void;
};

function futureDayLabel(dayKey: string, locale: string): string {
  const date = new Date(`${dayKey}T12:00:00`);
  if (!Number.isFinite(date.getTime())) return dayKey;
  return date.toLocaleDateString(locale, {
    weekday: "long",
    month: "short",
    day: "numeric",
  });
}

/** Virtualized To-do list, separated into compact day sections. */
export function TodosScrollList({
  rows,
  showEmpty,
  error,
  listHeader,
  refreshing = false,
  onRefresh,
  highlight,
  overlapNotes,
  busyTodoIds,
  onToggle,
  onDue,
  onDeleteItem,
}: Props) {
  const { t, i18n } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeTodosStyles(C), [C]);

  return (
    <FlashList
      data={rows}
      keyExtractor={todoListRowKey}
      getItemType={(row) => row.kind}
      style={s.list}
      contentContainerStyle={[
        showEmpty && !error ? s.listEmpty : undefined,
        s.listContent,
      ]}
      keyboardShouldPersistTaps="handled"
      refreshControl={
        onRefresh ? (
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.primary} />
        ) : undefined
      }
      ListHeaderComponent={listHeader}
      renderItem={({ item }) => {
        if (item.kind === "heading") {
          const title = item.section === "date" && item.dayKey
            ? futureDayLabel(item.dayKey, i18n.language)
            : t(`todos.group_${item.section}`);
          return (
            <View style={s.sectionHeader}>
              <Text style={s.sectionHeading}>{title}</Text>
              <Text style={s.sectionCount}>{item.count}</Text>
            </View>
          );
        }
        return (
          <TodoRow
            todo={item.todo}
            highlighted={highlight === item.todo.id}
            overlapWith={overlapNotes.get(item.todo.id)}
            busy={busyTodoIds.has(item.todo.id)}
            onToggle={onToggle}
            onDue={onDue}
            onDelete={onDeleteItem}
          />
        );
      }}
    />
  );
}
