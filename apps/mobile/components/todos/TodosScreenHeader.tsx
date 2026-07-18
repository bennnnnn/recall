import { useMemo } from "react";
import { Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { CalendarMeetingRow } from "@/components/CalendarMeetingRow";
import { ListGroupsView } from "@/components/ListGroupsView";
import { ReminderCalendar } from "@/components/ReminderCalendar";
import { StateView } from "@/components/StateView";
import { SuggestedReminderRow } from "@/components/SuggestedReminderRow";
import { TodoRow } from "@/components/todos/TodoRow";
import { makeTodosStyles } from "@/components/todos/todosStyles";
import type { TodosFocusSection } from "@/hooks/useTodosDerivedState";
import type {
  GoogleCalendarEvent,
  SuggestedReminder,
  Todo,
} from "@/lib/api";
import type { ListGroup } from "@/lib/listGroups";
import { useTheme } from "@/lib/theme";

type Props = {
  error: boolean;
  onRetry: () => void;
  focusSection: TodosFocusSection;
  showReminders: boolean;
  showList: boolean;
  showRemindersEmptyHero: boolean;
  isRemindersPage: boolean;
  openReminders: Todo[];
  calendarEvents: GoogleCalendarEvent[];
  suggestedReminders: SuggestedReminder[];
  selectedDay: string;
  visibleMonth: Date;
  onSelectDay: (dayKey: string) => void;
  onVisibleMonthChange: (month: Date) => void;
  calendarLoadError: boolean;
  onRetryCalendar: () => void;
  selectedDaySuggestions: SuggestedReminder[];
  selectedDayHeading: string;
  selectedDayMeetings: GoogleCalendarEvent[];
  selectedDayReminders: Todo[];
  suggestionBusyId: string | null;
  onAddSuggestion: (reminder: SuggestedReminder) => void;
  onDismissSuggestion: (reminder: SuggestedReminder) => void;
  highlight?: string;
  overlapNotes: Map<string, string>;
  togglingId: string | null;
  onToggle: (todo: Todo) => void;
  onDue: (todo: Todo) => void;
  onLinkProject?: (todo: Todo) => void;
  projectTitleById?: Map<string, string>;
  onDeleteItem: (todo: Todo) => void;
  listGroups: ListGroup[];
  focusTopic?: string;
  onReorderGroups: (topics: string[]) => void;
  onReorderItems: (topic: string, ordered: Todo[]) => void;
  onAddListItem: (topic: string, text: string) => void;
  onDeleteList: (topic: string) => void;
};

export function TodosScreenHeader({
  error,
  onRetry,
  focusSection,
  showReminders,
  showList,
  showRemindersEmptyHero,
  isRemindersPage,
  openReminders,
  calendarEvents,
  suggestedReminders,
  selectedDay,
  visibleMonth,
  onSelectDay,
  onVisibleMonthChange,
  calendarLoadError,
  onRetryCalendar,
  selectedDaySuggestions,
  selectedDayHeading,
  selectedDayMeetings,
  selectedDayReminders,
  suggestionBusyId,
  onAddSuggestion,
  onDismissSuggestion,
  highlight,
  overlapNotes,
  togglingId,
  onToggle,
  onDue,
  onLinkProject,
  projectTitleById,
  onDeleteItem,
  listGroups,
  focusTopic,
  onReorderGroups,
  onReorderItems,
  onAddListItem,
  onDeleteList,
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
          icon={focusSection === "list" ? "list-outline" : "notifications-outline"}
          title={focusSection === "list" ? t("lists.empty_title") : t("todos.empty_title")}
        />
      ) : null}

      {showReminders && isRemindersPage ? (
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
                  busy={togglingId === todo.id}
                  projectTitle={
                    todo.project_id && projectTitleById
                      ? projectTitleById.get(todo.project_id) ?? null
                      : null
                  }
                  onToggle={onToggle}
                  onDue={onDue}
                  onLinkProject={onLinkProject}
                  onDelete={onDeleteItem}
                />
              ))}
            </>
          )}
        </View>
      ) : null}

      {showReminders && !isRemindersPage && openReminders.length === 0 && !showRemindersEmptyHero ? (
        <Text style={s.sectionEmpty}>{t("todos.reminders_empty")}</Text>
      ) : null}

      {showList && listGroups.length > 0 ? (
        <ListGroupsView
          groups={listGroups}
          initialExpandedTopic={focusTopic}
          togglingId={togglingId}
          projectTitleById={projectTitleById}
          onReorderGroups={onReorderGroups}
          onReorderItems={onReorderItems}
          onToggle={onToggle}
          onAddItem={onAddListItem}
          onDeleteItem={onDeleteItem}
          onLinkProject={onLinkProject}
          onDeleteList={onDeleteList}
        />
      ) : null}
    </>
  );
}
