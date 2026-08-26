import { useCallback, useLayoutEffect, useMemo, useState } from "react";
import { Redirect, useLocalSearchParams, useNavigation } from "expo-router";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { useTranslation } from "react-i18next";

import { AddFab } from "@/components/AddFab";
import { ListGroupsView } from "@/components/ListGroupsView";
import { SkeletonList } from "@/components/SkeletonLoader";
import { AddReminderSheet } from "@/components/todos/AddReminderSheet";
import { DuePickerModal } from "@/components/todos/DuePickerModal";
import { NewListComposer } from "@/components/todos/NewListComposer";
import { TodosFlashList, TodosRemindersTail } from "@/components/todos/TodosFlashList";
import { TodosScreenHeader } from "@/components/todos/TodosScreenHeader";
import { makeTodosStyles } from "@/components/todos/todosStyles";
import { useTodosActions } from "@/hooks/useTodosActions";
import { useTodosCalendarIntegration } from "@/hooks/useTodosCalendarIntegration";
import { useTodosDerivedState } from "@/hooks/useTodosDerivedState";
import { useTodosListGroups } from "@/hooks/useTodosListGroups";
import { useAuth } from "@/contexts/AuthContext";
import { useTodos } from "@/contexts/TodosContext";
import { ensureNotificationPermission } from "@/lib/todos/todoReminders";
import { useTheme } from "@/lib/theme";

type FocusSection = "list" | "reminders";

export default function TodosScreen() {
  const { token, user } = useAuth();
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeTodosStyles(C), [C]);
  const navigation = useNavigation();
  const { focus, topic: focusTopic, highlight } = useLocalSearchParams<{
    focus?: string;
    topic?: string;
    highlight?: string;
  }>();
  const resolvedFocus = focus === "schedule" ? "reminders" : focus;
  const focusSection: FocusSection | null =
    resolvedFocus === "list" || resolvedFocus === "reminders" ? resolvedFocus : null;
  const showReminders = focusSection !== "list";
  const showList = focusSection !== "reminders";
  const {
    todos,
    setTodos,
    loading,
    error,
    refresh,
    markSeen,
  } = useTodos();
  const [reminderSheetOpen, setReminderSheetOpen] = useState(false);
  const [newListOpen, setNewListOpen] = useState(false);
  const [pullRefreshing, setPullRefreshing] = useState(false);

  const { groupOrder, persistGroupOrder, listGroups, hasNamedGroups } = useTodosListGroups(
    user?.id,
    todos,
    t("lists.default_group"),
  );

  const calendar = useTodosCalendarIntegration({
    token,
    focusSection,
    todos,
    highlight,
    refresh,
    markSeen,
    setTodos,
  });

  const {
    openReminders,
    visibleDone,
    isRemindersPage,
    showRemindersEmptyHero,
  } = useTodosDerivedState(todos, focusSection, listGroups, hasNamedGroups);

  const actions = useTodosActions({
    token,
    userId: user?.id,
    todos,
    setTodos,
    refresh,
    groupOrder,
    persistGroupOrder,
    goToDay: calendar.goToDay,
    isRemindersPage,
  });

  useLayoutEffect(() => {
    const title =
      focusSection === "list"
        ? t("drawer.lists")
        : focusSection === "reminders"
          ? t("todos.section_reminders")
          : t("todos.title");
    navigation.setOptions({
      title,
      headerRight: undefined,
    });
  }, [focusSection, navigation, t]);

  const onPullRefresh = useCallback(async () => {
    setPullRefreshing(true);
    await refresh({ silent: true, force: true });
    setPullRefreshing(false);
  }, [refresh]);

  const listsOwnScroll = showList && listGroups.length > 0 && !isRemindersPage;

  const listHeader = useMemo(
    () => (
      <TodosScreenHeader
        error={Boolean(error)}
        onRetry={refresh}
        focusSection={focusSection}
        showReminders={showReminders}
        showList={!listsOwnScroll && showList}
        showRemindersEmptyHero={showRemindersEmptyHero}
        isRemindersPage={isRemindersPage}
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
        listGroups={listGroups}
        focusTopic={focusTopic}
        onReorderGroups={actions.handleReorderGroups}
        onReorderItems={actions.handleReorderItems}
        onAddListItem={actions.handleCreateListItem}
        onDeleteList={actions.handleDeleteList}
      />
    ),
    [
      actions.busyTodoIds,
      actions.handleCreateListItem,
      actions.handleDeleteItem,
      actions.handleDeleteList,
      actions.handleReorderGroups,
      actions.handleReorderItems,
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
      focusSection,
      focusTopic,
      highlight,
      isRemindersPage,
      listGroups,
      listsOwnScroll,
      openReminders,
      refresh,
      showList,
      showReminders,
      showRemindersEmptyHero,
    ],
  );

  const remindersTail = useMemo(
    () => (
      <TodosRemindersTail
        showReminders={showReminders}
        isRemindersPage={isRemindersPage}
        openReminders={openReminders}
        visibleDone={visibleDone}
        focusSection={focusSection}
        busyTodoIds={actions.busyTodoIds}
        highlight={highlight}
        overlapNotes={calendar.overlapNotes}
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
      calendar.overlapNotes,
      focusSection,
      highlight,
      isRemindersPage,
      openReminders,
      showReminders,
      visibleDone,
    ],
  );

  if (!token) return <Redirect href="/login" />;

  if (loading && todos.length === 0) {
    return <SkeletonList />;
  }

  const openReminderSheet = () => {
    void ensureNotificationPermission();
    setReminderSheetOpen(true);
  };

  return (
    <GestureHandlerRootView style={s.root}>
      {showList && newListOpen ? (
        <NewListComposer
          saving={actions.creatingList}
          onCancel={() => setNewListOpen(false)}
          onSave={(name) => void actions.handleCreateList(name, () => setNewListOpen(false))}
        />
      ) : null}

      {listsOwnScroll ? (
        <ListGroupsView
          scrollEnabled
          groups={listGroups}
          initialExpandedTopic={focusTopic}
          busyTodoIds={actions.busyTodoIds}
          onReorderGroups={actions.handleReorderGroups}
          onReorderItems={actions.handleReorderItems}
          onToggle={actions.handleToggle}
          onAddItem={actions.handleCreateListItem}
          onDeleteItem={actions.handleDeleteItem}
          onDeleteList={actions.handleDeleteList}
          listHeader={listHeader}
          listFooter={showReminders ? remindersTail : null}
          refreshing={pullRefreshing}
          onRefresh={onPullRefresh}
        />
      ) : (
        <TodosFlashList
          showReminders={showReminders}
          isRemindersPage={isRemindersPage}
          openReminders={openReminders}
          visibleDone={visibleDone}
          focusSection={focusSection}
          busyTodoIds={actions.busyTodoIds}
          highlight={highlight}
          overlapNotes={calendar.overlapNotes}
          onToggle={actions.handleToggle}
          onDue={actions.openDuePicker}
          onDeleteItem={actions.handleDeleteItem}
          showRemindersEmptyHero={showRemindersEmptyHero}
          error={Boolean(error)}
          listHeader={listHeader}
          refreshing={pullRefreshing}
          onRefresh={onPullRefresh}
        />
      )}

      {isRemindersPage ? (
        <AddFab
          onPress={openReminderSheet}
          accessibilityLabel={t("todos.add_reminder")}
        />
      ) : null}
      {showList && !newListOpen && !isRemindersPage ? (
        <AddFab
          onPress={() => setNewListOpen(true)}
          accessibilityLabel={t("lists.new_group_a11y")}
        />
      ) : null}

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
