import { useLayoutEffect, useMemo, useState } from "react";
import { View } from "react-native";
import { Redirect, useLocalSearchParams, useNavigation } from "expo-router";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { useTranslation } from "react-i18next";

import { AddFab } from "@/components/AddFab";
import { Button } from "@/components/Button";
import { SkeletonList } from "@/components/SkeletonLoader";
import { AddReminderSheet } from "@/components/todos/AddReminderSheet";
import { DuePickerModal } from "@/components/todos/DuePickerModal";
import { NewListComposer } from "@/components/todos/NewListComposer";
import { TodosFlashList } from "@/components/todos/TodosFlashList";
import { TodosScreenHeader } from "@/components/todos/TodosScreenHeader";
import { makeTodosStyles } from "@/components/todos/todosStyles";
import { useTodosActions } from "@/hooks/useTodosActions";
import { useTodosCalendarIntegration } from "@/hooks/useTodosCalendarIntegration";
import { useTodosDerivedState } from "@/hooks/useTodosDerivedState";
import { useTodosListGroups } from "@/hooks/useTodosListGroups";
import { useAuth } from "@/contexts/AuthContext";
import { useTodos } from "@/contexts/TodosContext";
import { ensureNotificationPermission } from "@/lib/todoReminders";
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
  const focusSection: FocusSection | null =
    focus === "list" || focus === "reminders" ? focus : null;
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

  if (!token) return <Redirect href="/login" />;

  if (loading && todos.length === 0) {
    return <SkeletonList />;
  }

  const openReminderSheet = () => {
    void ensureNotificationPermission();
    setReminderSheetOpen(true);
  };

  const listHeader = (
    <TodosScreenHeader
      error={Boolean(error)}
      onRetry={() => void refresh()}
      focusSection={focusSection}
      showReminders={showReminders}
      showList={showList}
      showRemindersEmptyHero={showRemindersEmptyHero}
      onEmptyAction={
        focusSection === "list" ? () => setNewListOpen(true) : openReminderSheet
      }
      isRemindersPage={isRemindersPage}
      openReminders={openReminders}
      calendarEvents={calendar.calendarEvents}
      suggestedReminders={calendar.suggestedReminders}
      selectedDay={calendar.selectedDay}
      visibleMonth={calendar.visibleMonth}
      onSelectDay={calendar.goToDay}
      onVisibleMonthChange={calendar.setVisibleMonth}
      calendarLoadError={calendar.calendarLoadError}
      onRetryCalendar={() => void calendar.loadCalendarEvents()}
      selectedDaySuggestions={calendar.selectedDaySuggestions}
      selectedDayHeading={calendar.selectedDayHeading}
      selectedDayMeetings={calendar.selectedDayMeetings}
      selectedDayReminders={calendar.selectedDayReminders}
      suggestionBusyId={calendar.suggestionBusyId}
      onAddSuggestion={(reminder) => void calendar.handleAddSuggestion(reminder)}
      onDismissSuggestion={(reminder) => void calendar.handleDismissSuggestion(reminder)}
      highlight={highlight}
      overlapNotes={calendar.overlapNotes}
      togglingId={actions.togglingId}
      onToggle={(todo) => void actions.handleToggle(todo)}
      onDue={actions.openDuePicker}
      onDeleteItem={actions.handleDeleteItem}
      listGroups={listGroups}
      focusTopic={focusTopic}
      onReorderGroups={(topics) => void actions.handleReorderGroups(topics)}
      onReorderItems={(topic, ordered) => void actions.handleReorderItems(topic, ordered)}
      onAddListItem={(topic, text) => void actions.handleCreateListItem(topic, text)}
      onDeleteList={actions.handleDeleteList}
    />
  );

  return (
    <GestureHandlerRootView style={s.root}>
      {showReminders ? (
        <View style={s.topBar}>
          <Button
            title={t("todos.add_reminder")}
            onPress={openReminderSheet}
            style={s.topBtn}
          />
        </View>
      ) : null}

      {showList && newListOpen ? (
        <NewListComposer
          onCancel={() => setNewListOpen(false)}
          onSave={(name) => void actions.handleCreateList(name, () => setNewListOpen(false))}
        />
      ) : null}

      <TodosFlashList
        showReminders={showReminders}
        isRemindersPage={isRemindersPage}
        openReminders={openReminders}
        visibleDone={visibleDone}
        focusSection={focusSection}
        togglingId={actions.togglingId}
        highlight={highlight}
        overlapNotes={calendar.overlapNotes}
        onToggle={actions.handleToggle}
        onDue={actions.openDuePicker}
        onDeleteItem={actions.handleDeleteItem}
        showRemindersEmptyHero={showRemindersEmptyHero}
        error={Boolean(error)}
        listHeader={listHeader}
        refreshing={pullRefreshing}
        onRefresh={async () => {
          setPullRefreshing(true);
          await refresh({ silent: true, force: true });
          setPullRefreshing(false);
        }}
      />

      {showList && !newListOpen ? (
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
        onSave={(content, dueDate) =>
          void actions.handleCreateReminder(content, dueDate, () => setReminderSheetOpen(false))
        }
      />

      <DuePickerModal
        todos={todos}
        duePicker={actions.duePicker}
        onDismiss={() => actions.setDuePicker(null)}
        onChange={actions.onDuePickerChange}
        onConfirm={() => void actions.confirmDuePicker()}
      />
    </GestureHandlerRootView>
  );
}
