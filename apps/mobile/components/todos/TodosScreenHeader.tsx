import { useMemo } from "react";
import { ActivityIndicator, Pressable, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
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
  calendarLoading: boolean;
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
  onDeleteItem: (todo: Todo) => void;
  onNewList: () => void;
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
  calendarLoading,
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
  onDeleteItem,
  onNewList,
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
        <View style={s.empty}>
          <Ionicons
            name="cloud-offline-outline"
            size={48}
            color={C.textTertiary}
            style={s.emptyIcon}
          />
          <Text style={s.emptyTitle}>{t("common.error")}</Text>
          <Pressable style={s.retryBtn} onPress={onRetry}>
            <Text style={s.retryText}>{t("common.retry")}</Text>
          </Pressable>
        </View>
      ) : showRemindersEmptyHero ? (
        <View style={s.empty}>
          <View style={s.emptyIconWrap}>
            <Ionicons
              name={focusSection === "list" ? "list-outline" : "checkbox-outline"}
              size={28}
              color={C.primary}
            />
          </View>
          <Text style={s.emptyTitle}>
            {focusSection === "list" ? t("lists.empty_title") : t("todos.empty_title")}
          </Text>
          {focusSection === "list" ? (
            <Pressable style={s.emptyPrimaryBtn} onPress={onNewList}>
              <Ionicons name="add-circle-outline" size={20} color={C.primary} />
              <Text style={s.emptyPrimaryBtnText}>{t("lists.new_group")}</Text>
            </Pressable>
          ) : (
            <Text style={s.emptyBody}>{t("todos.empty_body")}</Text>
          )}
        </View>
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
          {calendarLoading ? (
            <View style={s.calendarLoading}>
              <ActivityIndicator size="small" color={C.primary} />
            </View>
          ) : null}
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
                  onToggle={() => onToggle(todo)}
                  onDue={() => onDue(todo)}
                  onDelete={() => onDeleteItem(todo)}
                />
              ))}
            </>
          )}
        </View>
      ) : null}

      {showReminders && !isRemindersPage && openReminders.length === 0 && !showRemindersEmptyHero ? (
        <Text style={s.sectionEmpty}>{t("todos.reminders_empty")}</Text>
      ) : null}

      {showList ? (
        <>
          {!(showRemindersEmptyHero && focusSection === "list") ? (
            <Pressable style={s.newListLink} onPress={onNewList}>
              <Ionicons name="add-circle-outline" size={20} color={C.primary} />
              <Text style={s.newListLinkText}>{t("lists.new_group")}</Text>
            </Pressable>
          ) : null}
          {listGroups.length > 0 ? (
            <ListGroupsView
              groups={listGroups}
              initialExpandedTopic={focusTopic}
              togglingId={togglingId}
              onReorderGroups={onReorderGroups}
              onReorderItems={onReorderItems}
              onToggle={onToggle}
              onAddItem={onAddListItem}
              onDeleteItem={onDeleteItem}
              onDeleteList={onDeleteList}
            />
          ) : null}
        </>
      ) : null}
    </>
  );
}
