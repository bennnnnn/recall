import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactElement } from "react";
import { Redirect, useLocalSearchParams, useNavigation } from "expo-router";
import { Keyboard, Pressable, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { AddFab } from "@/ui/controls/AddFab";
import { SkeletonList } from "@/ui/feedback/SkeletonLoader";
import { HeaderButton } from "@/ui/controls/HeaderButton";
import { plainHeaderItems, StackBackButton } from "@/ui/controls/StackBackButton";
import { TodosListHeader } from "@/features/todos/components/TodosListHeader";
import { TodoDetailMenu } from "@/features/todos/components/TodoDetailMenu";
import { TodoEditorSheet, type TodoEditorHandle } from "@/features/todos/components/TodoEditorSheet";
import { TodoSelectionBar } from "@/features/todos/components/TodoSelectionBar";
import { TodosScrollList } from "@/features/todos/components/TodosScrollList";
import { TodosViewMenu } from "@/features/todos/components/TodosViewMenu";
import { makeTodosStyles } from "@/features/todos/components/todosStyles";
import { useTodosActions } from "@/features/todos/hooks/useTodosActions";
import { useTodosDerivedState } from "@/features/todos/hooks/useTodosDerivedState";
import { useSuggestedReminders } from "@/features/todos/hooks/useSuggestedReminders";
import { useAccountViewOwner } from "@/hooks/useAccountViewOwner";
import { useAuth } from "@/contexts/AuthContext";
import { useTodos } from "@/features/todos/context/TodosContext";
import { buildTodoListRows } from "@/features/todos/model/todoListRows";
import { todosForView, type TodoView } from "@/features/todos/model/todoListFilter";
import { useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";
import { confirmDialog } from "@/ui/overlay/dialogs";

export default function TodosScreen() {
  const view = useAccountViewOwner();
  return <TodosContent key={view.key} isCurrentView={view.isCurrent} />;
}

function TodosContent({ isCurrentView }: { isCurrentView: () => boolean }) {
  const { token, user, updateUser } = useAuth();
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
  const [menuOpen, setMenuOpen] = useState(false);
  const [detailMenu, setDetailMenu] = useState(false);
  const editRef = useRef<TodoEditorHandle>(null);
  /** Header ⋮ — both the list menu and the detail menu drop from it. */
  const menuAnchorRef = useRef<View>(null);
  const [view, setView] = useState<TodoView>("all");
  const [selecting, setSelecting] = useState(false);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
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

  const leaveSelection = useCallback(() => {
    setSelecting(false);
    setSelectedIds([]);
  }, []);

  const editingId = actions.editingTodo?.id ?? null;
  const closeEditor = actions.closeTodoEditor;
  useEffect(() => {
    if (!editingId) return;
    if (!todos.some((row) => row.id === editingId)) {
      setDetailMenu(false);
      closeEditor();
    }
  }, [editingId, todos, closeEditor]);

  const detailOpen = editingId != null;
  const leaveDetail = useCallback(() => {
    setDetailMenu(false);
    editRef.current?.leave();
  }, []);
  // The native header keeps the first button it mounted. Route the press
  // through a ref so that button still opens this page's menu.
  const headerRightAction = useRef<() => void>(() => {});
  const headerBackAction = useRef<() => void>(() => {});
  headerBackAction.current = leaveDetail;
  useEffect(() => {
    if (!detailOpen) return;
    return navigation.addListener("beforeRemove", (event) => {
      const type = event.data.action.type;
      if (type !== "GO_BACK" && type !== "POP") return;
      event.preventDefault();
      leaveDetail();
    });
  }, [navigation, detailOpen, leaveDetail]);
  headerRightAction.current = () => {
    Keyboard.dismiss();
    if (detailOpen && editingId) {
      setDetailMenu((open) => !open);
      return;
    }
    if (selecting) {
      leaveSelection();
      return;
    }
    setMenuOpen((open) => !open);
  };

  useLayoutEffect(() => {
    const headerLeftElement = detailOpen ? (
      <HeaderButton
        icon="arrow-left"
        variant="plain"
        accessibilityLabel={t("common.back")}
        onPress={() => headerBackAction.current()}
      />
    ) : (
      <StackBackButton />
    );
    let headerRightElement: ReactElement | null = null;
    if (!(detailOpen && !editingId)) {
      headerRightElement = !detailOpen && selecting ? (
        <Pressable
          onPress={() => headerRightAction.current()}
          accessibilityRole="button"
          accessibilityLabel={t("todos.selection_done")}
          hitSlop={12}
        >
          <Text style={[Type.body, { color: C.primary }]}>{t("todos.selection_done")}</Text>
        </Pressable>
      ) : (
        <HeaderButton
          ref={menuAnchorRef}
          icon="more-horizontal"
          variant="plain"
          accessibilityLabel={detailOpen ? t("todos.detail_menu") : t("todos.menu")}
          onPress={() => headerRightAction.current()}
        />
      );
    }
    navigation.setOptions({
      title: t("drawer.reminders"),
      headerStyle: { backgroundColor: detailOpen ? C.surface : C.bg },
      headerShadowVisible: false,
      headerLeft: () => headerLeftElement,
      unstable_headerLeftItems: () => plainHeaderItems(headerLeftElement),
      headerRight: () => headerRightElement,
      unstable_headerRightItems: () => plainHeaderItems(headerRightElement),
    });
  }, [navigation, t, selecting, detailOpen, editingId, C.primary, C.surface, C.bg]);

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

  const visibleTodos = useMemo(() => todosForView(todos, view), [todos, view]);
  const rows = useMemo(() => {
    const suggestions = view === "all" || view === "open" ? suggestedReminders : [];
    return buildTodoListRows(visibleTodos, new Date(), suggestions);
  }, [visibleTodos, view, suggestedReminders]);
  const selected = useMemo(() => new Set(selectedIds), [selectedIds]);
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
    setMenuOpen(false);
    setDetailMenu(false);
    actions.closeTodoEditor();
    setEditorOpen(true);
  };

  const openTodo = (todo: Parameters<typeof actions.openTodoEditor>[0]) => {
    if (!isCurrentView()) return;
    setMenuOpen(false);
    setDetailMenu(false);
    setEditorOpen(false);
    actions.openTodoEditor(todo);
  };

  const toggleSelected = (todo: { id: string }) => {
    setSelectedIds((current) =>
      current.includes(todo.id) ? current.filter((id) => id !== todo.id) : [...current, todo.id],
    );
  };

  const deleteSelected = () => {
    if (selectedIds.length === 0) return;
    void confirmDialog({
      title: t("todos.delete_many", { count: selectedIds.length }),
      cancelLabel: t("common.cancel"),
      confirmLabel: t("common.delete"),
      destructive: true,
    }).then((ok) => {
      if (!ok) return;
      void actions.handleDeleteMany(selectedIds);
      leaveSelection();
    });
  };

  return (
    // The root layout already provides GestureHandlerRootView — a nested one
    // here steals gesture routing (see lessons: drawer pan vs mic press).
    <View style={s.root}>
      {detailOpen ? null : (
      <TodosScrollList
        rows={rows}
        showEmpty={showTodosEmptyHero && suggestedReminders.length === 0}
        error={Boolean(error)}
        listHeader={listHeader}
        refreshing={pullRefreshing}
        onRefresh={onPullRefresh}
        highlight={highlight}
        busyTodoIds={actions.busyTodoIds}
        busySuggestionIds={busySuggestionIds}
        onToggle={actions.handleToggle}
        onOpen={openTodo}
        onDeleteItem={actions.handleDeleteItem}
        onAddSuggestion={addSuggestion}
        onDismissSuggestion={dismissSuggestion}
        selecting={selecting}
        selectedIds={selected}
        onSelect={toggleSelected}
      />
      )}

      <TodosViewMenu
        visible={menuOpen && !selecting && !detailOpen}
        anchorRef={menuAnchorRef}
        view={view}
        onView={(next) => {
          setView(next);
          leaveSelection();
        }}
        onSelect={() => {
          setSelectedIds([]);
          setSelecting(true);
        }}
        onClose={() => setMenuOpen(false)}
      />

      {selecting ? (
        <TodoSelectionBar
          count={selectedIds.length}
          onComplete={() => {
            void actions.handleMarkDone(selectedIds);
            leaveSelection();
          }}
          onDelete={deleteSelected}
        />
      ) : detailOpen ? null : (
        <AddFab
          wave
          onPress={openEditor}
          accessibilityLabel={t("todos.add_todo")}
        />
      )}

      <TodoEditorSheet
        visible={editorOpen}
        saving={actions.savingTodo}
        todos={todos}
        onClose={() => { if (isCurrentView()) setEditorOpen(false); }}
        onSave={(content, dueDate, recurrence, topic) =>
          void actions.handleCreateTodo(
            content,
            dueDate,
            () => { if (isCurrentView()) setEditorOpen(false); },
            recurrence,
            topic,
          )
        }
      />

      <TodoEditorSheet
        page
        ref={editRef}
        visible={actions.editingTodo != null}
        editTodo={actions.editingTodo}
        readOnly={todos.find((todo) => todo.id === actions.editingTodo?.id)?.checked ?? actions.editingTodo?.checked ?? false}
        saving={
          actions.editingTodo
            ? actions.busyTodoIds.has(actions.editingTodo.id)
            : false
        }
        todos={todos}
        leadMinutes={user?.reminder_lead_minutes}
        onChangeLead={(minutes) => updateUser({ reminder_lead_minutes: minutes })}
        onClose={actions.closeTodoEditor}
        onSave={(content, dueDate, recurrence, topic) => {
          const target = actions.editingTodo;
          if (target) void actions.handleUpdateTodo(target, content, dueDate, recurrence, topic);
        }}
      />

      <TodoDetailMenu
        visible={detailMenu && actions.editingTodo != null}
        anchorRef={menuAnchorRef}
        checked={todos.find((todo) => todo.id === actions.editingTodo?.id)?.checked ?? actions.editingTodo?.checked ?? false}
        onMarkDone={() => {
          const current = todos.find((todo) => todo.id === actions.editingTodo?.id) ?? actions.editingTodo;
          setDetailMenu(false);
          if (!current) return;
          const draft = editRef.current?.pending() ?? null;
          void (async () => {
            if (draft) {
              const saved = await actions.handleUpdateTodo(
                current,
                draft.content,
                draft.dueDate,
                draft.recurrence,
                draft.topic,
                false,
              );
              if (!saved) return;
            }
            await actions.handleToggle(current);
          })();
        }}
        onDelete={() => {
          const current = todos.find((todo) => todo.id === actions.editingTodo?.id) ?? actions.editingTodo;
          setDetailMenu(false);
          if (current) actions.handleDeleteItem(current);
        }}
        onClose={() => setDetailMenu(false)}
      />
    </View>
  );
}
