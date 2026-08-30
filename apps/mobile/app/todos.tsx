import { useCallback, useLayoutEffect, useMemo, useState } from "react";
import { Redirect, useLocalSearchParams, useNavigation } from "expo-router";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { useTranslation } from "react-i18next";

import { AddFab } from "@/components/AddFab";
import { SkeletonList } from "@/components/SkeletonLoader";
import { AddReminderSheet } from "@/components/todos/AddReminderSheet";
import { DuePickerModal } from "@/components/todos/DuePickerModal";
import { TodosFlashList } from "@/components/todos/TodosFlashList";
import { TodosScreenHeader } from "@/components/todos/TodosScreenHeader";
import { makeTodosStyles } from "@/components/todos/todosStyles";
import { useTodosActions } from "@/hooks/useTodosActions";
import { useTodosCalendarIntegration } from "@/hooks/useTodosCalendarIntegration";
import { useTodosDerivedState } from "@/hooks/useTodosDerivedState";
import { useAuth } from "@/contexts/AuthContext";
import { useTodos } from "@/contexts/TodosContext";
import { ensureNotificationPermission } from "@/lib/todos/todoReminders";
import { useTheme } from "@/lib/theme";

export default function TodosScreen() {
  const { token, user } = useAuth();
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeTodosStyles(C), [C]);
  const navigation = useNavigation();
  const { focus, highlight } = useLocalSearchParams<{
    focus?: string;
    highlight?: string;
  }>();
  const {
    todos,
    setTodos,
    loading,
    error,
    refresh,
    markSeen,
  } = useTodos();
  const [reminderSheetOpen, setReminderSheetOpen] = useState(false);
  const [pullRefreshing, setPullRefreshing] = useState(false);

  const calendar = useTodosCalendarIntegration({
    token,
    todos,
    highlight,
    refresh,
    markSeen,
    setTodos,
    pushEnabled: user?.push_notifications_enabled ?? true,
  });

  const { openReminders, showRemindersEmptyHero } = useTodosDerivedState(todos);

  const actions = useTodosActions({
    token,
    userId: user?.id,
    pushEnabled: user?.push_notifications_enabled ?? true,
    todos,
    setTodos,
    refresh,
    goToDay: calendar.goToDay,
  });

  useLayoutEffect(() => {
    navigation.setOptions({
      title: t("drawer.reminders"),
      headerRight: undefined,
    });
  }, [navigation, t]);

  const onPullRefresh = useCallback(async () => {
    setPullRefreshing(true);
    await refresh({ silent: true, force: true });
    setPullRefreshing(false);
  }, [refresh]);

  const listHeader = useMemo(
    () => (
      <TodosScreenHeader
        error={Boolean(error)}
        onRetry={refresh}
        showRemindersEmptyHero={showRemindersEmptyHero}
        openReminders={openReminders}
        calendarEvents={calendar.calendarEvents}
        suggestedReminders={calendar.suggestedReminders}
        selectedDay={calendar.selectedDay}
        visibleMonth={calendar.visibleMonth}
        onSelectDay={calendar.goToDay}
        onVisibleMonthChange={calendar.setVisibleMonth}
        calendarLoadError={calendar.calendarLoadError}
        onRetryCalendar={calendar.loadCalendarEvents}
        suggestedLoadError={calendar.suggestedLoadError}
        onRetrySuggested={calendar.loadSuggestedReminders}
        selectedDaySuggestions={calendar.selectedDaySuggestions}
        selectedDayHeading={calendar.selectedDayHeading}
        selectedDayMeetings={calendar.selectedDayMeetings}
        selectedDayReminders={calendar.selectedDayReminders}
        suggestionBusyId={calendar.suggestionBusyId}
        onAddSuggestion={calendar.handleAddSuggestion}
        onDismissSuggestion={calendar.handleDismissSuggestion}
        highlight={highlight}
        overlapNotes={calendar.overlapNotes}
        busyTodoIds={actions.busyTodoIds}
        onToggle={actions.handleToggle}
        onDue={actions.openDuePicker}
        onDeleteItem={actions.handleDeleteItem}
      />
    ),
    [
      actions.busyTodoIds,
      actions.handleDeleteItem,
      actions.handleToggle,
      actions.openDuePicker,
      calendar.calendarEvents,
      calendar.calendarLoadError,
      calendar.goToDay,
      calendar.handleAddSuggestion,
      calendar.handleDismissSuggestion,
      calendar.loadCalendarEvents,
      calendar.loadSuggestedReminders,
      calendar.overlapNotes,
      calendar.selectedDay,
      calendar.selectedDayHeading,
      calendar.selectedDayMeetings,
      calendar.selectedDayReminders,
      calendar.selectedDaySuggestions,
      calendar.setVisibleMonth,
      calendar.suggestedLoadError,
      calendar.suggestedReminders,
      calendar.suggestionBusyId,
      calendar.visibleMonth,
      error,
      highlight,
      openReminders,
      refresh,
      showRemindersEmptyHero,
    ],
  );

  if (!token) return <Redirect href="/login" />;

  if (focus === "list") {
    return <Redirect href={{ pathname: "/todos", params: { focus: "reminders" } }} />;
  }

  if (loading && todos.length === 0) {
    return <SkeletonList />;
  }

  const openReminderSheet = () => {
    void ensureNotificationPermission();
    setReminderSheetOpen(true);
  };

  return (
    <GestureHandlerRootView style={s.root}>
      <TodosFlashList
        showRemindersEmptyHero={showRemindersEmptyHero}
        error={Boolean(error)}
        listHeader={listHeader}
        refreshing={pullRefreshing}
        onRefresh={onPullRefresh}
      />

      <AddFab
        onPress={openReminderSheet}
        accessibilityLabel={t("todos.add_reminder")}
      />

      <AddReminderSheet
        visible={reminderSheetOpen}
        saving={actions.savingReminder}
        todos={todos}
        onClose={() => setReminderSheetOpen(false)}
        onSave={(content, dueDate, recurrence) =>
          void actions.handleCreateReminder(
            content,
            dueDate,
            () => setReminderSheetOpen(false),
            recurrence,
          )
        }
      />

      <DuePickerModal
        todos={todos}
        duePicker={actions.duePicker}
        saving={
          actions.duePicker
            ? actions.busyTodoIds.has(actions.duePicker.todo.id)
            : false
        }
        onDismiss={() => actions.setDuePicker(null)}
        onChange={actions.onDuePickerChange}
        onConfirm={() => void actions.confirmDuePicker()}
      />
    </GestureHandlerRootView>
  );
}
