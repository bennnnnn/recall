import { useEffect, useMemo, useRef, type ReactElement, type RefObject } from "react";
import { RefreshControl, Text, View } from "react-native";
import { FlashList, type FlashListRef } from "@shopify/flash-list";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { TodoRow } from "@/features/todos/components/TodoRow";
import { TodoSectionHeading } from "@/features/todos/components/TodoSectionHeading";
import { makeTodosStyles } from "@/features/todos/components/todosStyles";
import type { Todo } from "@/lib/api";
import { formatDate } from "@/lib/datetime/format";
import { clashClusters, groupBySameTime, type ClashCluster } from "@/features/todos/model/reminderOverlap";
import { overdueAt } from "@/features/todos/model/dueDate";
import {
  todoListRowKey,
  type TodoListRow,
  type TodoSection,
} from "@/features/todos/model/todoListRows";
import { useTheme } from "@/lib/theme";
import { addFabClearance } from "@/ui/controls/addFabLayout";
import { Button } from "@/ui/controls/Button";
import type { Translate } from "@/lib/i18n/translate";

type Props = {
  rows: TodoListRow[];
  /** The to-do clock (useReminderClock): a time it has passed reads as overdue, a date alone
   * once its day has ended. */
  now: Date;
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
  /** Completed to-dos from before the last 30 days were left out: read them. Offered at the
   * end of the opened Completed section, which shows even with no recent ones for it. */
  onShowOlder?: () => void;
  /** Completed is open: its to-dos under its heading. It starts folded. */
  completedOpen: boolean;
  onToggleCompleted: () => void;
  /** A to-do to scroll on screen once its row is in the list (a new one, or one opened from
   * Home or a push); `onRevealed` once it has. */
  revealId?: string | null;
  onRevealed?: () => void;
};

type CardProps = Pick<Props, "now" | "highlight" | "busyTodoIds" | "onToggle" | "onOpen" | "onDeleteItem"
  | "selecting" | "selectedIds" | "onSelect"> & { section: TodoSection; todos: Todo[] };

/**
 * One list cell: a section's heading, or one card of to-dos due at the same time. A
 * cell per card, not per day, so FlashList mounts only the cards on screen: a day
 * of 300 to-dos used to be one cell that mounted all 300 rows.
 */
type TodoListItem =
  | { kind: "heading"; key: string; section: TodoSection; dayKey?: string; count: number }
  | { kind: "card"; key: string; section: TodoSection; todos: Todo[] };

const COMPLETED_KEY = todoListRowKey({ kind: "heading", section: "completed", key: "completed", count: 0 });

/** The cells, Completed's cards only while it is open; `olderHidden` heads Completed even with none recent. */
function itemsFromRows(rows: TodoListRow[], completedOpen: boolean, olderHidden: boolean): TodoListItem[] {
  const items: TodoListItem[] = [];
  let heading: Extract<TodoListRow, { kind: "heading" }> | null = null;
  let todos: Todo[] = [];
  const flush = () => {
    if (heading && todos.length) {
      const { section, dayKey } = heading;
      items.push({ kind: "heading", key: todoListRowKey(heading), section, dayKey, count: todos.length });
      if (section !== "completed" || completedOpen) {
        for (const group of groupBySameTime(todos)) {
          items.push({ kind: "card", key: todoListRowKey({ kind: "todo", todo: group[0]! }), section, todos: group });
        }
      }
    }
    todos = [];
  };
  for (const row of rows) {
    if (row.kind === "heading") {
      flush();
      heading = row;
      continue;
    }
    if (heading) todos.push(row.todo);
  }
  flush();
  if (olderHidden && !items.some((item) => item.key === COMPLETED_KEY)) {
    items.push({ kind: "heading", key: COMPLETED_KEY, section: "completed", count: 0 });
  }
  return items;
}

/** Scroll `revealId`'s card to the middle of the list once it is drawn, as a chat search hit is. */
function useRevealTodo(
  listRef: RefObject<FlashListRef<TodoListItem> | null>,
  items: TodoListItem[],
  revealId: string | null | undefined,
  onRevealed: (() => void) | undefined,
): void {
  useEffect(() => {
    if (!revealId) return;
    const index = items.findIndex((item) => item.kind === "card" && item.todos.some((todo) => todo.id === revealId));
    if (index < 0) return;
    // A frame later: the list lays out a row it has just been given before it can scroll to it.
    const frame = requestAnimationFrame(() => {
      void listRef.current?.scrollToIndex({ index, animated: true, viewPosition: 0.5 });
      onRevealed?.();
    });
    return () => cancelAnimationFrame(frame);
  }, [listRef, items, revealId, onRevealed]);
}

function joinNames(names: string[], locale: string): string {
  try {
    return new Intl.ListFormat(locale, { type: "conjunction", style: "long" }).format(names);
  } catch {
    return names.join(", ");
  }
}

function clashLines(clusters: ClashCluster[], locale: string, t: Translate): string[] {
  return clusters.map((cluster) => {
    const time = formatDate(new Date(cluster.at), "time");
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

/** One card of to-dos due at the same time, under the line that names any clash. */
function TodoCard({ section, todos, now, highlight, busyTodoIds, onToggle, onOpen, onDeleteItem, selecting = false,
  selectedIds, onSelect }: CardProps) {
  const { t, i18n } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeTodosStyles(C), [C]);
  const lines = clashLines(clashClusters(todos), i18n.language, t);
  return (
    <View>
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
        {todos.map((todo, todoIndex) => (
          <View key={todoListRowKey({ kind: "todo", todo })}>
            {todoIndex > 0 ? <View style={s.sheetRule} /> : null}
            <TodoRow
              todo={todo}
              section={section}
              pastDue={(overdueAt(todo) ?? Infinity) < now.getTime()}
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
}

/**
 * Virtualized To-do list, one list of sections: Overdue, Today, Tomorrow, each later day,
 * Anytime, then Completed folded under its count. Each heading, then its cards of same-time
 * to-dos.
 */
export function TodosScrollList({
  rows,
  now,
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
  completedOpen,
  onToggleCompleted,
  revealId,
  onRevealed,
}: Props) {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeTodosStyles(C), [C]);
  const olderHidden = Boolean(onShowOlder);
  const items = useMemo(() => itemsFromRows(rows, completedOpen, olderHidden), [rows, completedOpen, olderHidden]);
  const listRef = useRef<FlashListRef<TodoListItem>>(null);
  useRevealTodo(listRef, items, revealId, onRevealed);
  // The last row scrolls clear of the bottom-right add FAB.
  const insets = useSafeAreaInsets();
  const card = { now, highlight, busyTodoIds, onToggle, onOpen, onDeleteItem, selecting, selectedIds, onSelect };

  return (
    <FlashList
      ref={listRef}
      data={items}
      keyExtractor={(item) => item.key}
      getItemType={(item) => item.kind}
      style={s.list}
      contentContainerStyle={[
        items.length === 0 && !error ? s.listEmpty : undefined,
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
        // Completed is the last section: its end is the list's.
        onShowOlder && completedOpen ? (
          <View style={s.olderFooter}>
            <Button variant="ghost" size="sm" title={t("todos.show_older_completed")} onPress={onShowOlder} />
          </View>
        ) : null
      }
      renderItem={({ item, index }) => item.kind === "heading" ? (
        <TodoSectionHeading section={item.section} dayKey={item.dayKey} count={item.count} first={index === 0}
          completedOpen={completedOpen} onToggleCompleted={onToggleCompleted} />
      ) : (
        <TodoCard {...card} section={item.section} todos={item.todos} />
      )}
    />
  );
}
