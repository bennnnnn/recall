import { useMemo, type ReactElement } from "react";
import { RefreshControl, Text, View } from "react-native";
import { FlashList } from "@shopify/flash-list";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { TodoRow } from "@/features/todos/components/TodoRow";
import { makeTodosStyles } from "@/features/todos/components/todosStyles";
import type { Todo } from "@/lib/api";
import { formatClockTime } from "@/lib/datetime/format";
import { clashClusters, groupBySameTime, type ClashCluster } from "@/features/todos/model/reminderOverlap";
import {
  todoListRowKey,
  type TodoListRow,
  type TodoSection,
} from "@/features/todos/model/todoListRows";
import { useTheme } from "@/lib/theme";
import { addFabClearance } from "@/ui/controls/addFabLayout";
import { Button } from "@/ui/controls/Button";

type Props = {
  rows: TodoListRow[];
  /** The to-do clock (useReminderClock): a time it has passed reads as overdue. */
  now: Date;
  showEmpty: boolean;
  error: boolean;
  listHeader: ReactElement;
  refreshing?: boolean;
  onRefresh?: () => void;
  highlight?: string;
  busyTodoIds: ReadonlySet<string>;
  onToggle: (todo: Todo) => void;
  onOpen: (todo: Todo) => void;
  onDeleteItem: (todo: Todo) => void;
  selecting?: boolean;
  selectedIds?: ReadonlySet<string>;
  onSelect?: (todo: Todo) => void;
  /** Completed to-dos from before the last 30 days were left out: read them. */
  onShowOlder?: () => void;
};

type SheetBlock = {
  kind: "sheet";
  key: string;
  section: TodoSection;
  dayKey?: string;
  todos: Todo[];
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

function blocksFromRows(rows: TodoListRow[]): SheetBlock[] {
  const blocks: SheetBlock[] = [];
  let sheet: SheetBlock | null = null;
  const flush = () => {
    if (sheet && sheet.todos.length) blocks.push(sheet);
    sheet = null;
  };
  for (const row of rows) {
    if (row.kind === "heading") {
      flush();
      sheet = { kind: "sheet", key: row.key, section: row.section, dayKey: row.dayKey, todos: [] };
      continue;
    }
    sheet?.todos.push(row.todo);
  }
  flush();
  return blocks;
}

function joinNames(names: string[], locale: string): string {
  try {
    return new Intl.ListFormat(locale, { type: "conjunction", style: "long" }).format(names);
  } catch {
    return names.join(", ");
  }
}

function clashLines(clusters: ClashCluster[], locale: string, t: (key: string, options?: Record<string, string>) => string): string[] {
  return clusters.map((cluster) => {
    const time = formatClockTime(new Date(cluster.at), locale);
    if (cluster.names.length === 2) {
      return t("todos.day_clash_pair", {
        first: cluster.names[0] ?? "",
        second: cluster.names[1] ?? "",
        time,
      });
    }
    return t("todos.day_clash_many", { names: joinNames(cluster.names, locale), time });
  });
}

/** Virtualized To-do list. Each day is one sheet. */
export function TodosScrollList({
  rows,
  now,
  showEmpty,
  error,
  listHeader,
  refreshing = false,
  onRefresh,
  highlight,
  busyTodoIds,
  onToggle,
  onOpen,
  onDeleteItem,
  selecting = false,
  selectedIds,
  onSelect,
  onShowOlder,
}: Props) {
  const { t, i18n } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeTodosStyles(C), [C]);
  const blocks = useMemo(() => blocksFromRows(rows), [rows]);
  // The last row scrolls clear of the bottom-right add FAB.
  const insets = useSafeAreaInsets();

  return (
    <FlashList
      data={blocks}
      keyExtractor={(block) => block.key}
      getItemType={(block) => block.kind}
      style={s.list}
      contentContainerStyle={[
        showEmpty && !error ? s.listEmpty : undefined,
        s.listContent,
        { paddingBottom: addFabClearance(insets.bottom) },
      ]}
      extraData={selecting ? [...(selectedIds ?? [])].join(",") : highlight ?? "browse"}
      keyboardShouldPersistTaps="handled"
      refreshControl={
        onRefresh ? (
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.primary} />
        ) : undefined
      }
      ListHeaderComponent={listHeader}
      ListFooterComponent={
        onShowOlder ? (
          <View style={s.olderFooter}>
            <Button variant="ghost" size="sm" title={t("todos.show_older_completed")} onPress={onShowOlder} />
          </View>
        ) : null
      }
      ListEmptyComponent={
        !showEmpty && !error ? (
          <Text style={s.filterEmpty}>{t("todos.filter_empty")}</Text>
        ) : null
      }
      renderItem={({ item, index }) => {
        const title = item.section === "date" && item.dayKey
          ? futureDayLabel(item.dayKey, i18n.language)
          : t(`todos.group_${item.section}`);
        const prominent = item.section === "today" || item.section === "overdue";
        const groups = groupBySameTime(item.todos);
        return (
          <View>
            <View style={[s.sectionHeader, index === 0 && s.sectionHeaderFirst]}>
              <Text style={prominent ? s.dayHeading : s.sectionHeading}>{title}</Text>
            </View>
            {groups.map((group, groupIndex) => {
              const lines = clashLines(clashClusters(group), i18n.language, t);
              return (
                <View key={group[0]?.id ?? `${item.key}-${groupIndex}`}>
                  <View style={s.daySheet}>
                    {lines.length ? (
                      <View style={s.dayClash}>
                        {lines.map((line) => (
                          <Text key={line} style={s.dayClashText}>
                            {line}
                          </Text>
                        ))}
                      </View>
                    ) : null}
                    {group.map((todo, todoIndex) => (
                      <View key={todoListRowKey({ kind: "todo", todo })}>
                        {todoIndex > 0 ? <View style={s.sheetRule} /> : null}
                        <TodoRow
                          todo={todo}
                          section={item.section}
                          pastDue={todo.due_at != null && Date.parse(todo.due_at) < now.getTime()}
                          highlighted={highlight === todo.id}
                          busy={busyTodoIds.has(todo.id)}
                          onToggle={onToggle}
                          onOpen={onOpen}
                          onDelete={onDeleteItem}
                          selecting={selecting}
                          selected={selectedIds?.has(todo.id) ?? false}
                          onSelect={onSelect}
                        />
                      </View>
                    ))}
                  </View>
                </View>
              );
            })}
          </View>
        );
      }}
    />
  );
}
