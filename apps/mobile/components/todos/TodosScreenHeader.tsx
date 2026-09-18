import { useMemo } from "react";
import { View } from "react-native";
import { useTranslation } from "react-i18next";

import { ReminderCalendar } from "@/components/ReminderCalendar";
import { StateView } from "@/components/StateView";
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
};

/** Schedule header: hero states + calendar. The day-items body is the
 *  virtualized TodosScrollList below — do not add rows back here. */
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
          icon="calendar-outline"
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
      </View>
    </>
  );
}
