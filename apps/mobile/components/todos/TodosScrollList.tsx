import { useMemo, type ReactElement } from "react";
import { RefreshControl, Text } from "react-native";
import { FlashList } from "@shopify/flash-list";
import { useTranslation } from "react-i18next";

import { CalendarMeetingRow } from "@/components/CalendarMeetingRow";
import { SuggestedReminderRow } from "@/components/SuggestedReminderRow";
import { TodoRow } from "@/components/todos/TodoRow";
import { makeTodosStyles } from "@/components/todos/todosStyles";
import type { SuggestedReminder, Todo } from "@/lib/api";
import { scheduleRowKey, type ScheduleRow } from "@/lib/todos/dayListRows";
import { useTheme } from "@/lib/theme";

type Props = {
  rows: ScheduleRow[];
  showRemindersEmptyHero: boolean;
  error: boolean;
  listHeader: ReactElement;
  refreshing?: boolean;
  onRefresh?: () => void;
  highlight?: string;
  overlapNotes: Map<string, string>;
  busyTodoIds: ReadonlySet<string>;
  suggestionBusyId: string | null;
  onToggle: (todo: Todo) => void;
  onDue: (todo: Todo) => void;
  onDeleteItem: (todo: Todo) => void;
  onAddSuggestion: (reminder: SuggestedReminder) => void;
  onDismissSuggestion: (reminder: SuggestedReminder) => void;
};

/** Schedule screen: calendar/header on top, virtualized day-items body. */
export function TodosScrollList({
  rows,
  showRemindersEmptyHero,
  error,
  listHeader,
  refreshing = false,
  onRefresh,
  highlight,
  overlapNotes,
  busyTodoIds,
  suggestionBusyId,
  onToggle,
  onDue,
  onDeleteItem,
  onAddSuggestion,
  onDismissSuggestion,
}: Props) {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeTodosStyles(C), [C]);

  return (
    <FlashList
      data={rows}
      keyExtractor={scheduleRowKey}
      getItemType={(row) => row.kind}
      style={s.list}
      contentContainerStyle={[
        showRemindersEmptyHero && !error ? s.listEmpty : undefined,
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
        switch (item.kind) {
          case "suggestionsHeading":
            return <Text style={s.sectionHeading}>{t("calendar.from_email")}</Text>;
          case "suggestion":
            return (
              <SuggestedReminderRow
                reminder={item.reminder}
                busy={suggestionBusyId === item.reminder.id}
                onAdd={() => onAddSuggestion(item.reminder)}
                onDismiss={() => onDismissSuggestion(item.reminder)}
              />
            );
          case "dayHeading":
            return <Text style={s.dayHeading}>{item.heading}</Text>;
          case "emptyDay":
            return <Text style={s.sectionEmpty}>{t("calendar.no_items_day")}</Text>;
          case "meeting":
            return <CalendarMeetingRow event={item.event} />;
          case "reminder":
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
        }
      }}
    />
  );
}
