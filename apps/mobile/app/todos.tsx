import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  Text,
  View,
} from "react-native";
import { FlashList } from "@shopify/flash-list";
import { Ionicons } from "@expo/vector-icons";
import { Redirect, useLocalSearchParams, useNavigation } from "expo-router";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { useTranslation } from "react-i18next";

import { useTheme } from "@/lib/theme";
import { useAuth } from "@/contexts/AuthContext";
import { useTodos } from "@/contexts/TodosContext";
import { Todo } from "@/lib/api";
import {
  ensureNotificationPermission,
} from "@/lib/todoReminders";
import { CalendarMeetingRow } from "@/components/CalendarMeetingRow";
import { SuggestedReminderRow } from "@/components/SuggestedReminderRow";
import { ListGroupsView } from "@/components/ListGroupsView";
import { ReminderCalendar } from "@/components/ReminderCalendar";
import { StateView } from "@/components/StateView";
import { AddReminderSheet } from "@/components/todos/AddReminderSheet";
import { DuePickerModal } from "@/components/todos/DuePickerModal";
import { NewListSheet } from "@/components/todos/NewListSheet";
import { TodoRow } from "@/components/todos/TodoRow";
import {
  isReminder,
  sortOpen,
} from "@/components/todos/todoHelpers";
import { makeTodosStyles } from "@/components/todos/todosStyles";
import { useTodosActions } from "@/hooks/useTodosActions";
import { useTodosCalendarIntegration } from "@/hooks/useTodosCalendarIntegration";
import { useTodosListGroups } from "@/hooks/useTodosListGroups";

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

  const { groupOrder, persistGroupOrder, listGroups, hasNamedGroups } = useTodosListGroups(
    user?.id,
    todos,
    t("lists.default_group"),
  );

  const {
    selectedDay,
    visibleMonth,
    setVisibleMonth,
    goToDay,
    calendarEvents,
    calendarLoadError,
    calendarLoading,
    loadCalendarEvents,
    suggestedReminders,
    suggestionBusyId,
    handleAddSuggestion,
    handleDismissSuggestion,
    overlapNotes,
    selectedDayReminders,
    selectedDayMeetings,
    selectedDaySuggestions,
    selectedDayHeading,
  } = useTodosCalendarIntegration({
    token,
    focusSection,
    todos,
    highlight,
    todosCount: todos.length,
    refresh,
    markSeen,
    setTodos,
  });

  const openReminders = useMemo(
    () => sortOpen(todos.filter((item) => isReminder(item) && !item.checked)),
    [todos],
  );
  const doneItems = useMemo(
    () =>
      [...todos]
        .filter((item) => item.checked)
        .sort((a, b) => b.created_at.localeCompare(a.created_at)),
    [todos],
  );
  const doneReminders = useMemo(
    () => doneItems.filter((item) => isReminder(item)),
    [doneItems],
  );
  const visibleDone = useMemo(() => {
    if (focusSection === "list" || focusSection === "reminders") return [];
    return doneReminders;
  }, [doneReminders, focusSection]);
  const hasListItems = todos.some((item) => !isReminder(item));
  const isEmpty = useMemo(() => {
    if (focusSection === "list") {
      return listGroups.length === 0;
    }
    if (focusSection === "reminders") {
      return openReminders.length === 0 && doneReminders.length === 0;
    }
    return (
      openReminders.length === 0 && !hasListItems && doneReminders.length === 0 && !hasNamedGroups
    );
  }, [
    doneReminders.length,
    focusSection,
    hasListItems,
    hasNamedGroups,
    openReminders.length,
  ]);
  const isRemindersPage = focusSection === "reminders";
  const showRemindersEmptyHero = isEmpty && focusSection !== "reminders";

  const {
    togglingId,
    duePicker,
    setDuePicker,
    savingReminder,
    handleCreateListItem,
    handleCreateList,
    handleReorderGroups,
    handleReorderItems,
    handleCreateReminder,
    handleToggle,
    handleDeleteItem,
    handleDeleteList,
    openDuePicker,
    onDuePickerChange,
    confirmDuePicker,
  } = useTodosActions({
    token,
    userId: user?.id,
    todos,
    setTodos,
    refresh,
    groupOrder,
    persistGroupOrder,
    goToDay,
    isRemindersPage,
  });

  useEffect(() => {
    const title =
      focusSection === "list"
        ? ""
        : focusSection === "reminders"
          ? t("todos.section_reminders")
          : t("todos.title");
    navigation.setOptions({ title });
  }, [focusSection, navigation, t]);

  // The screen is a multi-mode dashboard. The genuinely long, flat lists are
  // `openReminders` (non-calendar mode) and `visibleDone` — those go into the
  // FlashList data so rows are recycled. The calendar day-view, ListGroupsView,
  // and the new-group link are bounded/structured, so they render in the header.
  // (These hooks must run before the early returns below — rules-of-hooks.)
  type TodoListItem =
    | { type: "remindersHeader"; key: string; title: string }
    | { type: "doneHeader"; key: string; title: string }
    | { type: "todoRow"; key: string; todo: Todo; done: boolean };

  const todosData = useMemo<TodoListItem[]>(() => {
    const items: TodoListItem[] = [];
    if (showReminders && !isRemindersPage && openReminders.length > 0) {
      if (!focusSection) {
        items.push({
          type: "remindersHeader",
          key: "reminders-h",
          title: t("todos.section_reminders"),
        });
      }
      for (const todo of openReminders) {
        items.push({ type: "todoRow", key: todo.id, todo, done: false });
      }
    }
    if (visibleDone.length > 0) {
      items.push({
        type: "doneHeader",
        key: "done-h",
        title: `${t("todos.done")} (${visibleDone.length})`,
      });
      for (const todo of visibleDone) {
        items.push({ type: "todoRow", key: todo.id, todo, done: true });
      }
    }
    return items;
  }, [showReminders, isRemindersPage, openReminders, focusSection, visibleDone, t]);

  const renderTodoItem = useCallback(
    ({ item }: { item: TodoListItem }) => {
      if (item.type === "remindersHeader" || item.type === "doneHeader") {
        return <Text style={s.sectionHeading}>{item.title}</Text>;
      }
      const todo = item.todo;
      if (item.done) {
        return (
          <TodoRow
            key={todo.id}
            todo={todo}
            busy={togglingId === todo.id}
            onToggle={() => void handleToggle(todo)}
            onDue={isReminder(todo) ? () => openDuePicker(todo) : undefined}
            onDelete={() => handleDeleteItem(todo)}
          />
        );
      }
      return (
        <TodoRow
          key={todo.id}
          todo={todo}
          highlighted={highlight === todo.id}
          overlapWith={overlapNotes.get(todo.id)}
          busy={togglingId === todo.id}
          onToggle={() => void handleToggle(todo)}
          onDue={() => openDuePicker(todo)}
          onDelete={() => handleDeleteItem(todo)}
        />
      );
    },
    [s, togglingId, highlight, overlapNotes, handleToggle, openDuePicker, handleDeleteItem],
  );

  if (!token) return <Redirect href="/login" />;

  if (loading) {
    return (
      <View style={s.center}>
        <ActivityIndicator size="large" color={C.primary} />
      </View>
    );
  }

  // The screen is a multi-mode dashboard. The genuinely long, flat lists are
  // `openReminders` (non-calendar mode) and `visibleDone` — those go into the
  // FlashList data so rows are recycled. The calendar day-view, ListGroupsView,
  // and the new-group link are bounded/structured, so they render in the header.
  const todosHeader = (
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
          <Pressable
            style={s.retryBtn}
            onPress={() => {
              void refresh();
            }}
          >
            <Text style={s.retryText}>{t("common.retry")}</Text>
          </Pressable>
        </View>
      ) : showRemindersEmptyHero ? (
        <View style={s.empty}>
          <Ionicons
            name={focusSection === "list" ? "list-outline" : "checkbox-outline"}
            size={48}
            color={C.primary}
            style={s.emptyIcon}
          />
          <Text style={s.emptyTitle}>{t("todos.empty_title")}</Text>
          <Text style={s.emptyBody}>
            {focusSection === "list"
              ? t("todos.empty_list_body")
              : t("todos.empty_body")}
          </Text>
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
            onSelectDay={goToDay}
            onVisibleMonthChange={setVisibleMonth}
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
              onRetry={() => void loadCalendarEvents()}
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
                  onAdd={() => void handleAddSuggestion(reminder)}
                  onDismiss={() => void handleDismissSuggestion(reminder)}
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
                  highlighted={highlight === todo.id}
                  overlapWith={overlapNotes.get(todo.id)}
                  busy={togglingId === todo.id}
                  onToggle={() => void handleToggle(todo)}
                  onDue={() => openDuePicker(todo)}
                  onDelete={() => handleDeleteItem(todo)}
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
          <Pressable style={s.newListLink} onPress={() => setNewListOpen(true)}>
            <Ionicons name="add-circle-outline" size={20} color={C.primary} />
            <Text style={s.newListLinkText}>{t("lists.new_group")}</Text>
          </Pressable>
          <ListGroupsView
            groups={listGroups}
            initialExpandedTopic={focusTopic ?? undefined}
            togglingId={togglingId}
            onReorderGroups={(topics) => void handleReorderGroups(topics)}
            onReorderItems={(topic, ordered) => void handleReorderItems(topic, ordered)}
            onToggle={(todo) => void handleToggle(todo)}
            onAddItem={(topic, text) => void handleCreateListItem(topic, text)}
            onDeleteItem={handleDeleteItem}
            onDeleteList={handleDeleteList}
          />
        </>
      ) : null}
    </>
  );

  return (
    <GestureHandlerRootView style={s.root}>
      {showReminders ? (
      <View style={s.topBar}>
          <Pressable
            style={[s.topBtn, s.topBtnSolo]}
            onPress={() => {
              void ensureNotificationPermission();
              setReminderSheetOpen(true);
            }}
          >
            <Ionicons name="notifications-outline" size={20} color={C.primary} />
            <Text style={s.topBtnText}>{t("todos.add_reminder")}</Text>
          </Pressable>
      </View>
      ) : null}

      <FlashList
        style={s.list}
        data={todosData}
        renderItem={renderTodoItem}
        keyExtractor={(item) => item.key}
        getItemType={(item) => item.type}
        contentContainerStyle={showRemindersEmptyHero && !error ? s.listEmpty : undefined}
        keyboardShouldPersistTaps="handled"
        ListHeaderComponent={todosHeader}
      />

      <NewListSheet
        visible={newListOpen}
        onClose={() => setNewListOpen(false)}
        onSave={(name) => void handleCreateList(name, () => setNewListOpen(false))}
      />

      <AddReminderSheet
        visible={reminderSheetOpen}
        saving={savingReminder}
        todos={todos}
        onClose={() => setReminderSheetOpen(false)}
        onSave={(content, dueDate) =>
          void handleCreateReminder(content, dueDate, () => setReminderSheetOpen(false))
        }
      />

      <DuePickerModal
        todos={todos}
        duePicker={duePicker}
        onDismiss={() => setDuePicker(null)}
        onChange={onDuePickerChange}
        onConfirm={() => void confirmDuePicker()}
      />
    </GestureHandlerRootView>
  );
}
