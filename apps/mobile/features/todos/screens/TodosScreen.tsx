import { useCallback, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Redirect, useLocalSearchParams, useNavigation } from "expo-router";
import { View } from "react-native";
import { useTranslation } from "react-i18next";

import { AddFab } from "@/components/AddFab";
import { SkeletonList } from "@/components/SkeletonLoader";
import { TodosListHeader } from "@/features/todos/components/TodosListHeader";
import { TodoEditorSheet } from "@/features/todos/components/TodoEditorSheet";
import { TodosScrollList } from "@/features/todos/components/TodosScrollList";
import { makeTodosStyles } from "@/features/todos/components/todosStyles";
import { useTodosActions } from "@/features/todos/hooks/useTodosActions";
import { useTodosDerivedState } from "@/features/todos/hooks/useTodosDerivedState";
import { useSuggestedReminders } from "@/features/todos/hooks/useSuggestedReminders";
import { useAccountViewOwner } from "@/hooks/useAccountViewOwner";
import { useAuth } from "@/contexts/AuthContext";
import { useTodos } from "@/features/todos/context/TodosContext";
import { buildReminderOverlapNotes } from "@/features/todos/model/reminderOverlap";
import { buildTodoListRows } from "@/features/todos/model/todoListRows";
import { useTheme } from "@/lib/theme";

export default function TodosScreen() {
  const view = useAccountViewOwner();
  return <TodosContent key={view.key} isCurrentView={view.isCurrent} />;
}

function TodosContent({ isCurrentView }: { isCurrentView: () => boolean }) {
  const { token, user } = useAuth();
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeTodosStyles(C), [C]);
  const navigation = useNavigation();
  const { focus, highlight, eventTitle, eventStart } = useLocalSearchParams<{
    focus?: string;
    highlight?: string;
    eventTitle?: string;
    eventStart?: string;
  }>();
  const {
    todos,
    setTodos,
    loading,
    error,
    refresh,
    markSeenIds,
    getTodos,
    isCurrentSession,
  } = useTodos();
  const [editorOpen, setEditorOpen] = useState(false);
  const [pullRefreshing, setPullRefreshing] = useState(false);
  const refreshingRef = useRef(false);

  const { showTodosEmptyHero } = useTodosDerivedState(todos);

  const actions = useTodosActions({
    token,
    userId: user?.id,
    todos,
    getTodos,
    isCurrentSession,
    isCurrentView,
    markSeenIds,
    setTodos,
    refresh,
  });
  const {
    reminders: suggestedReminders,
    busyIds: busySuggestionIds,
    refresh: refreshSuggestions,
    add: addSuggestion,
    dismiss: dismissSuggestion,
  } = useSuggestedReminders({
    token,
    isCurrentSession,
    isCurrentView,
    setTodos,
    refreshTodos: refresh,
  });

  useLayoutEffect(() => {
    navigation.setOptions({
      title: t("drawer.reminders"),
      headerRight: undefined,
    });
  }, [navigation, t]);

  const onPullRefresh = useCallback(async () => {
    if (!isCurrentView() || refreshingRef.current) return;
    refreshingRef.current = true;
    setPullRefreshing(true);
    try {
      await Promise.all([
        refresh({ silent: true, force: true }),
        refreshSuggestions(),
      ]);
    }
    finally {
      refreshingRef.current = false;
      if (isCurrentView()) setPullRefreshing(false);
    }
  }, [refresh, refreshSuggestions, isCurrentView]);

  const retry = useCallback(() => {
    if (isCurrentView()) void refresh({ force: true });
  }, [refresh, isCurrentView]);

  const listHeader = useMemo(
    () => (
      <TodosListHeader
        error={Boolean(error)}
        onRetry={retry}
        showEmpty={showTodosEmptyHero && suggestedReminders.length === 0}
        calendarNudge={
          typeof eventTitle === "string" && typeof eventStart === "string"
            ? { title: eventTitle, startAt: eventStart }
            : null
        }
      />
    ),
    [error, retry, showTodosEmptyHero, suggestedReminders.length, eventTitle, eventStart],
  );

  const rows = useMemo(
    () => buildTodoListRows(todos, new Date(), suggestedReminders),
    [todos, suggestedReminders],
  );
  const overlapNotes = useMemo(() => buildReminderOverlapNotes(todos), [todos]);

  if (!token) return <Redirect href="/login" />;

  // Legacy links used focus=list; the list is the only view now.
  if (focus === "list") {
    return <Redirect href="/todos" />;
  }

  if (loading && todos.length === 0) {
    return <SkeletonList />;
  }

  const openEditor = () => {
    if (!isCurrentView()) return;
    setEditorOpen(true);
  };

  return (
    // The root layout already provides GestureHandlerRootView — a nested one
    // here steals gesture routing (see lessons: drawer pan vs mic press).
    <View style={s.root}>
      <TodosScrollList
        rows={rows}
        showEmpty={showTodosEmptyHero}
        error={Boolean(error)}
        listHeader={listHeader}
        refreshing={pullRefreshing}
        onRefresh={onPullRefresh}
        highlight={highlight}
        overlapNotes={overlapNotes}
        busyTodoIds={actions.busyTodoIds}
        busySuggestionIds={busySuggestionIds}
        onToggle={actions.handleToggle}
        onDue={actions.openTodoEditor}
        onDeleteItem={actions.handleDeleteItem}
        onAddSuggestion={addSuggestion}
        onDismissSuggestion={dismissSuggestion}
      />

      <AddFab
        onPress={openEditor}
        accessibilityLabel={t("todos.add_todo")}
      />

      <TodoEditorSheet
        visible={editorOpen}
        saving={actions.savingTodo}
        todos={todos}
        onClose={() => { if (isCurrentView()) setEditorOpen(false); }}
        onSave={(content, dueDate, recurrence) =>
          void actions.handleCreateTodo(
            content,
            dueDate,
            () => { if (isCurrentView()) setEditorOpen(false); },
            recurrence,
          )
        }
      />

      <TodoEditorSheet
        visible={actions.editingTodo != null}
        editTodo={actions.editingTodo}
        saving={
          actions.editingTodo
            ? actions.busyTodoIds.has(actions.editingTodo.id)
            : false
        }
        todos={todos}
        onClose={actions.closeTodoEditor}
        onSave={(content, dueDate, recurrence) => {
          const target = actions.editingTodo;
          if (target) void actions.handleUpdateTodo(target, content, dueDate, recurrence);
        }}
      />
    </View>
  );
}
