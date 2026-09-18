import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Alert } from "react-native";
import { useTranslation } from "react-i18next";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { dayKeyForDue } from "@/components/todos/todoHelpers";
import { api, type RecurrenceRule, type Todo } from "@/lib/api";
import { getSessionGeneration } from "@/lib/auth";
import { toDueAtIso } from "@/lib/todos/dueDate";
import { markReminderIdsSeen } from "@/lib/reminderSeen";
import { buildOptimisticTodo, removeTodoById, replaceTodoById } from "@/lib/todos/optimisticTodo";
import { beginTodoMutation, getTodoMutationState } from "@/lib/todos/todoMutationState";
import { DEFAULT_TOPIC } from "@/lib/todoTopics";

type Params = {
  token: string | null;
  userId: string | undefined;
  pushEnabled?: boolean;
  todos: Todo[];
  getTodos?: () => Todo[];
  isCurrentSession?: () => boolean;
  isCurrentView?: () => boolean;
  markSeenIds?: (ids: string[]) => Promise<void>;
  setTodos: React.Dispatch<React.SetStateAction<Todo[]>>;
  refresh: (opts?: { silent?: boolean; force?: boolean; afterPending?: boolean }) => Promise<void>;
  goToDay: (dayKey: string) => void;
};
const alwaysCurrent = () => true;

export function useTodosActions({ token, userId, todos, getTodos,
  isCurrentSession = alwaysCurrent, isCurrentView = alwaysCurrent, markSeenIds,
  setTodos, refresh, goToDay,
}: Params) {
  const { t } = useTranslation();
  const feedback = useActionFeedbackOptional();
  const session = getSessionGeneration();
  const signedIn = Boolean(token);
  const owner = useMemo(() => ({ session, signedIn, userId,
    mutations: getTodoMutationState(`${session}:${userId ?? ""}`),
  }), [session, signedIn, userId]);
  const ownerRef = useRef(owner);
  ownerRef.current = owner;
  const todosRef = useRef(todos);
  todosRef.current = todos;
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);
  const isSameOwner = useCallback(() => owner.signedIn && ownerRef.current === owner &&
    getSessionGeneration() === owner.session && isCurrentSession(), [owner, isCurrentSession]);
  const canAct = useCallback(() => mounted.current && isSameOwner() && isCurrentView(),
    [isSameOwner, isCurrentView]);
  const [, redraw] = useState(0);
  useEffect(() => {
    const changed = () => { if (mounted.current && isSameOwner()) redraw((value) => value + 1); };
    owner.mutations.listeners.add(changed);
    return () => { owner.mutations.listeners.delete(changed); };
  }, [owner, isSameOwner]);
  const [editorState, setEditorState] = useState<{ owner: typeof owner; value: Todo | null }>({ owner, value: null });
  const editorRef = useRef(editorState);
  const editingReminder = editorState.owner === owner ? editorState.value : null;
  const setEditingReminder = useCallback((todo: Todo | null) => {
    if (!canAct()) return;
    const next = { owner, value: todo };
    editorRef.current = next;
    setEditorState(next);
  }, [canAct, owner]);
  const reportError = useCallback((bodyKey: string) => {
    if (!canAct()) return;
    if (feedback) feedback.error(t(bodyKey));
    else Alert.alert(t("todos.error"), t(bodyKey));
  }, [canAct, feedback, t]);
  const latestTodo = useCallback((id: string) => (getTodos?.() ?? todosRef.current).find((item) => item.id === id), [getTodos]);
  const applyTodos = useCallback((update: (rows: Todo[]) => Todo[]) => {
    if (isSameOwner()) setTodos(update);
  }, [isSameOwner, setTodos]);
  const reconcile = useCallback(() => {
    if (isSameOwner()) void refresh({ silent: true, force: true, afterPending: true });
  }, [isSameOwner, refresh]);

  const mutateRow = useCallback(async (
    id: string, change: (snapshot: Todo) => Todo | null,
    request: (snapshot: Todo) => Promise<Todo | null>, errorKey: string,
    navigation?: { optimistic: (snapshot: Todo) => void; saved: (updated: Todo) => void; rollback: (snapshot: Todo) => void },
    kind: "row" | "toggle" = "row",
  ): Promise<boolean> => {
    if (!canAct()) return false;
    const snapshot = latestTodo(id);
    if (!snapshot) return false;
    const release = beginTodoMutation(owner.mutations, id, kind);
    if (!release) return false;
    const optimistic = change(snapshot);
    applyTodos((rows) => optimistic ? replaceTodoById(rows, id, optimistic) : removeTodoById(rows, id));
    if (canAct()) navigation?.optimistic(snapshot);
    try {
      const updated = await request(snapshot);
      applyTodos((rows) => updated ? replaceTodoById(rows, id, updated) : removeTodoById(rows, id));
      if (updated && canAct()) navigation?.saved(updated);
      return true;
    } catch {
      applyTodos((rows) => replaceTodoById(rows, id, snapshot));
      if (canAct()) navigation?.rollback(snapshot);
      reportError(errorKey);
      return false;
    } finally {
      release();
      reconcile();
    }
  }, [canAct, latestTodo, owner, applyTodos, reportError, reconcile]);

  const handleCreateReminder = useCallback(async (
    content: string, dueDate: Date, onCreated: () => void, recurrence: RecurrenceRule | null = null,
  ) => {
    if (!token || !canAct()) return;
    const trimmed = content.trim();
    if (!trimmed) return;
    if (!Number.isFinite(dueDate.getTime())) { reportError("todos.error_create"); return; }
    const dueIso = toDueAtIso(dueDate);
    const optimistic = buildOptimisticTodo({ content: trimmed, topic: DEFAULT_TOPIC, dueAt: dueIso, recurrenceRule: recurrence });
    const release = beginTodoMutation(owner.mutations, optimistic.id, "create");
    if (!release) return;
    applyTodos((rows) => [optimistic, ...rows]);
    goToDay(dayKeyForDue(dueDate, dueIso));
    try {
      const created = await api.createTodo(token, trimmed, DEFAULT_TOPIC, { dueAt: dueIso, recurrenceRule: recurrence });
      applyTodos((rows) => replaceTodoById(rows, optimistic.id, created));
      if (isSameOwner()) {
        if (markSeenIds) void markSeenIds([created.id]);
        else if (userId) void markReminderIdsSeen(userId, [created.id]);
      }
      if (canAct()) {
        goToDay(dayKeyForDue(dueDate, created.due_at ?? dueIso));
        onCreated();
      }
    } catch {
      applyTodos((rows) => removeTodoById(rows, optimistic.id));
      reportError("todos.error_create");
    } finally {
      release();
      reconcile();
    }
  }, [token, canAct, reportError, owner, applyTodos, goToDay, isSameOwner, markSeenIds, userId, reconcile]);

  const handleToggle = useCallback(async (todo: Todo) => {
    if (!token) return;
    await mutateRow(todo.id, (snapshot) => ({ ...snapshot, checked: !snapshot.checked }),
      (snapshot) => api.updateTodo(token, todo.id, { checked: !snapshot.checked }), "todos.error_toggle", undefined, "toggle");
  }, [token, mutateRow]);

  const handleDeleteItem = useCallback((todo: Todo) => {
    if (!token || !canAct() || owner.mutations.pendingIds.has(todo.id)) return;
    const current = latestTodo(todo.id);
    if (!current) return;
    Alert.alert(t("todos.delete_confirm"), t("todos.delete_confirm_body", { title: current.content }), [
      { text: t("common.cancel"), style: "cancel" },
      { text: t("common.delete"), style: "destructive", onPress: async () => {
        await mutateRow(todo.id, () => null, async () => {
          await api.deleteTodo(token, todo.id);
          return null;
        }, "todos.error_delete");
      } },
    ]);
  }, [token, canAct, owner, latestTodo, t, mutateRow]);

  const openReminderEditor = useCallback((todo: Todo) => {
    if (!canAct() || owner.mutations.pendingIds.has(todo.id)) return;
    const current = latestTodo(todo.id);
    if (!current) return;
    setEditingReminder(current);
  }, [canAct, owner, latestTodo, setEditingReminder]);

  const closeReminderEditor = useCallback(() => {
    setEditingReminder(null);
  }, [setEditingReminder]);

  // Saves content + due + repeat from the edit sheet. The todo argument must
  // still be the open target — a retained callback from a replaced target
  // must not save (see useTodosActionsSafety tests).
  const handleUpdateReminder = useCallback(async (
    todo: Todo, content: string, date: Date, recurrence: RecurrenceRule | null,
  ): Promise<boolean> => {
    if (!token || !canAct()) return false;
    if (editorRef.current.owner !== owner || editorRef.current.value?.id !== todo.id) return false;
    const trimmed = content.trim();
    if (!trimmed) return false;
    if (!Number.isFinite(date.getTime())) { reportError("todos.error_due"); return false; }
    const dueIso = toDueAtIso(date);
    const saved = await mutateRow(todo.id, (snapshot) => ({
      ...snapshot, content: trimmed, due_at: dueIso, recurrence_rule: recurrence,
    }),
      () => api.updateTodo(token, todo.id, {
        content: trimmed, due_at: dueIso, recurrence_rule: recurrence,
      }), "todos.error_due", {
        optimistic: () => goToDay(dayKeyForDue(date, dueIso)),
        saved: (updated) => goToDay(dayKeyForDue(date, updated.due_at ?? dueIso)),
        rollback: (snapshot) => {
          if (snapshot.due_at) goToDay(dayKeyForDue(new Date(snapshot.due_at), snapshot.due_at));
        },
      });
    if (saved && editorRef.current.value?.id === todo.id) setEditingReminder(null);
    return saved;
  }, [token, canAct, owner, reportError, mutateRow, goToDay, setEditingReminder]);

  return {
    togglingId: owner.mutations.togglingIds.values().next().value ?? null,
    busyTodoIds: new Set(owner.mutations.pendingIds),
    editingReminder, savingReminder: owner.mutations.createId !== null,
    handleCreateReminder, handleToggle, handleDeleteItem, openReminderEditor,
    closeReminderEditor, handleUpdateReminder,
  };
}
