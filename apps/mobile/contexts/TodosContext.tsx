import { createContext, useContext, useEffect, type ReactNode } from "react";
import { useAuthOptional } from "@/contexts/AuthContext";
import { useTodosList } from "@/hooks/useTodosList";
import { useTodoReminderState } from "@/hooks/useTodoReminderState";
import { getSessionGeneration } from "@/lib/auth";
import { syncTodoReminders } from "@/lib/todos/todoReminders";

type TodosContextValue = ReturnType<typeof useTodosList> & ReturnType<typeof useTodoReminderState>;
const TodosContext = createContext<TodosContextValue | null>(null);

export function TodosProvider({ children }: { children: ReactNode }) {
  const auth = useAuthOptional();
  const list = useTodosList(auth?.token, auth?.user?.id);
  const leadMinutes = auth?.user?.reminder_lead_minutes ?? undefined;
  const pushEnabled = auth?.user?.push_notifications_enabled ?? true;
  const reminders = useTodoReminderState({ userId: auth?.user?.id, leadMinutes,
    todos: list.todos, retainedOpenIds: list.retainedOpenIds, getTodos: list.getTodos, isCurrentSession: list.isCurrentSession });
  const session = getSessionGeneration();
  const { todos, loaded, isCurrentSession } = list;
  useEffect(() => {
    if (!loaded || !isCurrentSession()) return;
    void syncTodoReminders(todos, { pushEnabled, session, leadMinutes })
      .catch(() => { if (isCurrentSession()) console.warn("[todos] device reminder sync failed"); });
  }, [todos, loaded, isCurrentSession, pushEnabled, session, leadMinutes]);
  const value = { ...list, ...reminders, remindersReady: reminders.remindersReady && !list.loading };
  return <TodosContext.Provider value={value}>{children}</TodosContext.Provider>;
}

export function useTodos() {
  const ctx = useContext(TodosContext);
  if (!ctx) throw new Error("useTodos must be used within TodosProvider");
  return ctx;
}
export function useTodosOptional() { return useContext(TodosContext); }
