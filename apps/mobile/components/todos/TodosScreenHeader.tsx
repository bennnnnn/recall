import { useMemo } from "react";
import { Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { CalendarMeetingRow } from "@/components/CalendarMeetingRow";
import { ReminderCalendar } from "@/components/ReminderCalendar";
import { StateView } from "@/components/StateView";
import { SuggestedReminderRow } from "@/components/SuggestedReminderRow";
import { TodoRow } from "@/components/todos/TodoRow";
import { makeTodosStyles } from "@/components/todos/todosStyles";
import type {
  GoogleCalendarEvent,
  SuggestedReminder,
  Todo,
} from "@/lib/api";
import { useTheme } from "@/lib/theme";

type Props = {
  error: boolean;
  onRetry: () => void;
  showRemindersEmptyHero: boolean;
  openReminders: Todo[];
  calendarEvents: GoogleCalendarEvent[];
  suggestedReminders: SuggestedReminder[];
  selectedDay: string;
  visibleMonth: Date;
  onSelectDay: (dayKey: string) => void;
  onVisibleMonthChange: (month: Date) => void;
  calendarLoadError: boolean;
  onRetryCalendar: () => void;
  suggestedLoadError: boolean;
  onRetrySuggested: () => void;
  selectedDaySuggestions: SuggestedReminder[];
  selectedDayHeading: string;
  selectedDayMeetings: GoogleCalendarEvent[];
  selectedDayReminders: Todo[];
  suggestionBusyId: string | null;
  onAddSuggestion: (reminder: SuggestedReminder) => void;
  onDismissSuggestion: (reminder: SuggestedReminder) => void;
  highlight?: string;
  overlapNotes: Map<string, string>;
  busyTodoIds: ReadonlySet<string>;
  onToggle: (todo: Todo) => void;
  onDue: (todo: Todo) => void;
  onDeleteItem: (todo: Todo) => void;
};

export function TodosScreenHeader({
  error,
  onRetry,
  showRemindersEmptyHero,
  openReminders,
  calendarEvents,
  suggestedReminders,
  selectedDay,
  visibleMonth,
  onSelectDay,
  onVisibleMonthChange,
  calendarLoadError,
  onRetryCalendar,
  suggestedLoadError,
  onRetrySuggested,
  selectedDaySuggestions,
  selectedDayHeading,
  selectedDayMeetings,
  selectedDayReminders,
  suggestionBusyId,
  onAddSuggestion,
  onDismissSuggestion,
  highlight,
  overlapNotes,
  busyTodoIds,
  onToggle,
  onDue,
  onDeleteItem,
}: Props) {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeTodosStyles(C), [C]);

  return (
    <>
      {error ? (
        <StateView
          variant="error"
          title={t("common.error")}
          onRetry={onRetry}
          retryLabel={t("common.retry")}
        />
      ) : showRemindersEmptyHero ? (
        <StateView
          variant="empty"
          icon="notifications-outline"
          title={t("todos.empty_title")}
        />
      ) : null}

      <View style={s.section}>
        <ReminderCalendar
          reminders={openReminders}
          calendarEvents={calendarEvents}
          suggestedReminders={suggestedReminders}
          selectedDay={selectedDay}
          visibleMonth={visibleMonth}
          onSelectDay={onSelectDay}
          onVisibleMonthChange={onVisibleMonthChange}
        />
        {calendarLoadError ? (
          <StateView
            variant="error"
            compact
            message={t("calendar.load_failed")}
            onRetry={onRetryCalendar}
            retryLabel={t("common.retry")}
          />
        ) : null}
        {suggestedLoadError ? (
          <StateView
            variant="error"
            compact
            message={t("common.error")}
            onRetry={onRetrySuggested}
            retryLabel={t("common.retry")}
          />
        ) : null}
        {selectedDaySuggestions.length > 0 ? (
          <>
            <Text style={s.sectionHeading}>{t("calendar.from_email")}</Text>
            {selectedDaySuggestions.map((reminder) => (
              <SuggestedReminderRow
                key={reminder.id}
                reminder={reminder}
                busy={suggestionBusyId === reminder.id}
                onAdd={() => onAddSuggestion(reminder)}
                onDismiss={() => onDismissSuggestion(reminder)}
              />
            ))}
          </>
        ) : null}
        <Text style={s.dayHeading}>{selectedDayHeading}</Text>
        {selectedDayMeetings.length === 0 &&
        selectedDayReminders.length === 0 &&
        selectedDaySuggestions.length === 0 ? (
          <Text style={s.sectionEmpty}>{t("calendar.no_items_day")}</Text>
        ) : (
          <>
            {selectedDayMeetings.map((event) => (
              <CalendarMeetingRow key={event.id} event={event} />
            ))}
            {selectedDayReminders.map((todo) => (
              <TodoRow
                key={todo.id}
                todo={todo}
                variant="open"
                highlighted={highlight === todo.id}
                overlapWith={overlapNotes.get(todo.id)}
                busy={busyTodoIds.has(todo.id)}
                onToggle={onToggle}
                onDue={onDue}
                onDelete={onDeleteItem}
              />
            ))}
          </>
        )}
      </View>
    </>
  );
}
