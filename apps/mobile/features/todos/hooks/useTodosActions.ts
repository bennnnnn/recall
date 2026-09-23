import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Alert } from "react-native";
import { useTranslation } from "react-i18next";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { api, type RecurrenceRule, type Todo } from "@/lib/api";
import { getSessionGeneration } from "@/lib/auth";
import { toDueAtIso } from "@/features/todos/model/dueDate";
import { markReminderIdsSeen } from "@/features/todos/model/reminderSeen";
import { buildOptimisticTodo, removeTodoById, replaceTodoById } from "@/features/todos/model/optimisticTodo";
import { beginTodoMutation, getTodoMutationState } from "@/features/todos/model/todoMutationState";
import { DEFAULT_TOPIC } from "@/features/todos/model/todoTopics";

type Params = {
  token: string | null;
  userId: string | undefined;
  todos: Todo[];
  getTodos?: () => Todo[];
  isCurrentSession?: () => boolean;
  isCurrentView?: () => boolean;
  markSeenIds?: (ids: string[]) => Promise<void>;
  setTodos: React.Dispatch<React.SetStateAction<Todo[]>>;
  refresh: (opts?: { silent?: boolean; force?: boolean; afterPending?: boolean }) => Promise<void>;
};
const alwaysCurrent = () => true;

export function useTodosActions({ token, userId, todos, getTodos,
  isCurrentSession = alwaysCurrent, isCurrentView = alwaysCurrent, markSeenIds,
  setTodos, refresh,
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
  const editingTodo = editorState.owner === owner ? editorState.value : null;
  const setEditingTodo = useCallback((todo: Todo | null) => {
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
    kind: "row" | "toggle" = "row",
  ): Promise<boolean> => {
    if (!canAct()) return false;
    const snapshot = latestTodo(id);
    if (!snapshot) return false;
    const release = beginTodoMutation(owner.mutations, id, kind);
    if (!release) return false;
    const optimistic = change(snapshot);
    applyTodos((rows) => optimistic ? replaceTodoById(rows, id, optimistic) : removeTodoById(rows, id));
    try {
      const updated = await request(snapshot);
      applyTodos((rows) => updated ? replaceTodoById(rows, id, updated) : removeTodoById(rows, id));
      return true;
    } catch {
      applyTodos((rows) => replaceTodoById(rows, id, snapshot));
      reportError(errorKey);
      return false;
    } finally {
      release();
      reconcile();
    }
  }, [canAct, latestTodo, owner, applyTodos, reportError, reconcile]);

  const handleCreateTodo = useCallback(async (
    content: string,
    dueDate: Date | null,
    onCreated: () => void,
    recurrence: RecurrenceRule | null = null,
  ) => {
    if (!token || !canAct()) return;
    const trimmed = content.trim();
    if (!trimmed) return;
    if (dueDate && !Number.isFinite(dueDate.getTime())) {
      reportError("todos.error_create");
      return;
    }
    const dueIso = dueDate ? toDueAtIso(dueDate) : null;
    const recurrenceRule = dueIso ? recurrence : null;
    const optimistic = buildOptimisticTodo({
      content: trimmed,
      topic: DEFAULT_TOPIC,
      dueAt: dueIso,
      recurrenceRule,
    });
    const release = beginTodoMutation(owner.mutations, optimistic.id, "create");
    if (!release) return;
    applyTodos((rows) => [optimistic, ...rows]);
    try {
      const created = await api.createTodo(token, trimmed, DEFAULT_TOPIC, {
        dueAt: dueIso,
        recurrenceRule,
      });
      applyTodos((rows) => replaceTodoById(rows, optimistic.id, created));
      if (created.due_at && isSameOwner()) {
        if (markSeenIds) void markSeenIds([created.id]);
        else if (userId) void markReminderIdsSeen(userId, [created.id]);
      }
      if (canAct()) {
        onCreated();
      }
    } catch {
      applyTodos((rows) => removeTodoById(rows, optimistic.id));
      reportError("todos.error_create");
    } finally {
      release();
      reconcile();
    }
  }, [token, canAct, reportError, owner, applyTodos, isSameOwner, markSeenIds, userId, reconcile]);

  const handleToggle = useCallback(async (todo: Todo) => {
    if (!token) return;
    await mutateRow(todo.id, (snapshot) => ({ ...snapshot, checked: !snapshot.checked }),
      (snapshot) => api.updateTodo(token, todo.id, { checked: !snapshot.checked }), "todos.error_toggle", "toggle");
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

  const openTodoEditor = useCallback((todo: Todo) => {
    if (!canAct() || owner.mutations.pendingIds.has(todo.id)) return;
    const current = latestTodo(todo.id);
    if (!current) return;
    setEditingTodo(current);
  }, [canAct, owner, latestTodo, setEditingTodo]);

  const closeTodoEditor = useCallback(() => {
    setEditingTodo(null);
  }, [setEditingTodo]);

  // Saves content + due + repeat from the edit sheet. The todo argument must
  // still be the open target — a retained callback from a replaced target
  // must not save (see useTodosActionsSafety tests).
  const handleUpdateTodo = useCallback(async (
    todo: Todo, content: string, date: Date | null, recurrence: RecurrenceRule | null,
  ): Promise<boolean> => {
    if (!token || !canAct()) return false;
    if (editorRef.current.owner !== owner || editorRef.current.value?.id !== todo.id) return false;
    const trimmed = content.trim();
    if (!trimmed) return false;
    if (date && !Number.isFinite(date.getTime())) {
      reportError("todos.error_due");
      return false;
    }
    const dueIso = date ? toDueAtIso(date) : null;
    const recurrenceRule = dueIso ? recurrence : null;
    const saved = await mutateRow(todo.id, (snapshot) => ({
      ...snapshot, content: trimmed, due_at: dueIso, recurrence_rule: recurrenceRule,
    }),
      () => api.updateTodo(token, todo.id, {
        content: trimmed, due_at: dueIso, recurrence_rule: recurrenceRule,
      }), "todos.error_due");
    if (saved && editorRef.current.value?.id === todo.id) setEditingTodo(null);
    return saved;
  }, [token, canAct, owner, reportError, mutateRow, setEditingTodo]);

  return {
    togglingId: owner.mutations.togglingIds.values().next().value ?? null,
    busyTodoIds: new Set(owner.mutations.pendingIds),
    editingTodo,
    savingTodo: owner.mutations.createId !== null,
    handleCreateTodo,
    handleToggle,
    handleDeleteItem,
    openTodoEditor,
    closeTodoEditor,
    handleUpdateTodo,
  };
}
