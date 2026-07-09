import { useEffect, useMemo, useState } from "react";
import { Pressable, ScrollView, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Redirect, useLocalSearchParams, useNavigation } from "expo-router";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { useTranslation } from "react-i18next";

import { SkeletonList } from "@/components/SkeletonLoader";
import { AddReminderSheet } from "@/components/todos/AddReminderSheet";
import { DuePickerModal } from "@/components/todos/DuePickerModal";
import { NewListSheet } from "@/components/todos/NewListSheet";
import { TodosFlashList } from "@/components/todos/TodosFlashList";
import { TodosScreenHeader } from "@/components/todos/TodosScreenHeader";
import { makeTodosStyles } from "@/components/todos/todosStyles";
import { useTodosActions } from "@/hooks/useTodosActions";
import { useTodosCalendarIntegration } from "@/hooks/useTodosCalendarIntegration";
import { useTodosDerivedState } from "@/hooks/useTodosDerivedState";
import { useTodosListGroups } from "@/hooks/useTodosListGroups";
import { useAuth } from "@/contexts/AuthContext";
import { useTodos } from "@/contexts/TodosContext";
import { api, type Project } from "@/lib/api";
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
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectFilterId, setProjectFilterId] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    void (async () => {
      try {
        const list = await api.listProjects(token);
        if (!cancelled) {
          setProjects(list.filter((project) => !project.archived));
        }
      } catch {
        if (!cancelled) setProjects([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  const projectTitleById = useMemo(
    () => new Map(projects.map((project) => [project.id, project.title])),
    [projects],
  );

  const filteredTodos = useMemo(() => {
    if (!projectFilterId) return todos;
    return todos.filter((item) => item.project_id === projectFilterId);
  }, [todos, projectFilterId]);

  const { groupOrder, persistGroupOrder, listGroups, hasNamedGroups } = useTodosListGroups(
    user?.id,
    filteredTodos,
    t("lists.default_group"),
  );

  const calendar = useTodosCalendarIntegration({
    token,
    focusSection,
    todos: filteredTodos,
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
  } = useTodosDerivedState(filteredTodos, focusSection, listGroups, hasNamedGroups);

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

  useEffect(() => {
    const title =
      focusSection === "list"
        ? ""
        : focusSection === "reminders"
          ? t("todos.section_reminders")
          : t("todos.title");
    navigation.setOptions({ title });
  }, [focusSection, navigation, t]);

  if (!token) return <Redirect href="/login" />;

  if (loading && todos.length === 0) {
    return <SkeletonList />;
  }

  const listHeader = (
    <>
      {projects.length > 0 ? (
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={s.projectFilterBar}
        >
          <Pressable
            style={[s.projectFilterChip, !projectFilterId && s.projectFilterChipActive]}
            onPress={() => setProjectFilterId(null)}
          >
            <Text
              style={[
                s.projectFilterChipText,
                !projectFilterId && s.projectFilterChipTextActive,
              ]}
            >
              {t("todos.filter_all_projects")}
            </Text>
          </Pressable>
          {projects.map((project) => {
            const active = projectFilterId === project.id;
            return (
              <Pressable
                key={project.id}
                style={[s.projectFilterChip, active && s.projectFilterChipActive]}
                onPress={() => setProjectFilterId(project.id)}
              >
                <Text
                  style={[
                    s.projectFilterChipText,
                    active && s.projectFilterChipTextActive,
                  ]}
                  numberOfLines={1}
                >
                  {project.title}
                </Text>
              </Pressable>
            );
          })}
        </ScrollView>
      ) : null}
      <TodosScreenHeader
        error={Boolean(error)}
        onRetry={() => void refresh()}
        focusSection={focusSection}
        showReminders={showReminders}
        showList={showList}
        showRemindersEmptyHero={showRemindersEmptyHero}
        isRemindersPage={isRemindersPage}
        openReminders={openReminders}
        calendarEvents={calendar.calendarEvents}
        suggestedReminders={calendar.suggestedReminders}
        selectedDay={calendar.selectedDay}
        visibleMonth={calendar.visibleMonth}
        onSelectDay={calendar.goToDay}
        onVisibleMonthChange={calendar.setVisibleMonth}
        calendarLoading={calendar.calendarLoading}
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
        onLinkProject={(todo) => actions.handleLinkProject(todo, projects)}
        projectTitleById={projectTitleById}
        onDeleteItem={actions.handleDeleteItem}
        onNewList={() => setNewListOpen(true)}
        listGroups={listGroups}
        focusTopic={focusTopic}
        onReorderGroups={(topics) => void actions.handleReorderGroups(topics)}
        onReorderItems={(topic, ordered) => void actions.handleReorderItems(topic, ordered)}
        onAddListItem={(topic, text) => void actions.handleCreateListItem(topic, text)}
        onDeleteList={actions.handleDeleteList}
      />
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
        onLinkProject={(todo) => actions.handleLinkProject(todo, projects)}
        projectTitleById={projectTitleById}
        onDeleteItem={actions.handleDeleteItem}
        showRemindersEmptyHero={showRemindersEmptyHero}
        error={Boolean(error)}
        listHeader={listHeader}
      />

      <NewListSheet
        visible={newListOpen}
        onClose={() => setNewListOpen(false)}
        onSave={(name) => void actions.handleCreateList(name, () => setNewListOpen(false))}
      />

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
