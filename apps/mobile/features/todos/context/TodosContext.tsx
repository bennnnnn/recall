import { createContext, useContext, useEffect, useMemo, type ReactNode } from "react";
import { useAuthOptional } from "@/contexts/AuthContext";
import { useTodosList } from "@/features/todos/hooks/useTodosList";
import { useTodoReminderState } from "@/features/todos/hooks/useTodoReminderState";
import { getSessionGeneration } from "@/lib/auth";
import { syncTodoReminders } from "@/features/todos/model/todoReminders";

type TodosContextValue = ReturnType<typeof useTodosList> & ReturnType<typeof useTodoReminderState>;
const TodosContext = createContext<TodosContextValue | null>(null);

export function TodosProvider({ children }: { children: ReactNode }) {
  const auth = useAuthOptional();
  const list = useTodosList(auth?.token, auth?.user?.id);
  const leadMinutes = auth?.user?.reminder_lead_minutes ?? undefined;
  const pushEnabled = auth?.user?.push_notifications_enabled ?? true;
  const remindersEnabled = auth?.user?.push_reminders_enabled ?? true;
  const reminders = useTodoReminderState({ userId: auth?.user?.id, leadMinutes,
    todos: list.todos, retainedOpenIds: list.retainedOpenIds, getTodos: list.getTodos, isCurrentSession: list.isCurrentSession });
  const session = getSessionGeneration();
  const {
    todos, loading, error, loaded, retainedOpenIds, olderCompleted, showOlderCompleted, setTodos, getTodos, refresh,
    isCurrentSession,
  } = list;
  useEffect(() => {
    if (!loaded || !isCurrentSession()) return;
    void syncTodoReminders(todos, { pushEnabled, remindersEnabled, session, leadMinutes })
      .catch(() => { if (isCurrentSession()) console.warn("[todos] device reminder sync failed"); });
  }, [todos, loaded, isCurrentSession, pushEnabled, remindersEnabled, session, leadMinutes]);
  const { unseenCount, showIndicator, seenReminderIds, homeNudgeDismissed, markSeen, markSeenIds,
    dismissReminderNudge } = reminders;
  const remindersReady = reminders.remindersReady && !loading;
  // Both hooks hand back a new object every render, and this provider renders on
  // every auth change. Rebuild the value only when a field does, so readers (the
  // chat screen among them) do not render along with it.
  const value = useMemo<TodosContextValue>(() => ({
    todos, loading, error, loaded, retainedOpenIds, olderCompleted, showOlderCompleted, setTodos, getTodos, refresh,
    isCurrentSession, unseenCount, showIndicator, remindersReady, seenReminderIds, homeNudgeDismissed, markSeen,
    markSeenIds, dismissReminderNudge,
  }), [todos, loading, error, loaded, retainedOpenIds, olderCompleted, showOlderCompleted, setTodos, getTodos,
    refresh, isCurrentSession, unseenCount, showIndicator, remindersReady, seenReminderIds, homeNudgeDismissed,
    markSeen, markSeenIds, dismissReminderNudge]);
  return <TodosContext.Provider value={value}>{children}</TodosContext.Provider>;
}

export function useTodos() {
  const ctx = useContext(TodosContext);
  if (!ctx) throw new Error("useTodos must be used within TodosProvider");
  return ctx;
}
export function useTodosOptional() { return useContext(TodosContext); }
