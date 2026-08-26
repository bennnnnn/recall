import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type Dispatch,
  type ReactNode,
  type SetStateAction,
} from "react";
import { AppState, type AppStateStatus } from "react-native";

import { useAuthOptional } from "@/contexts/AuthContext";
import { api, type Todo } from "@/lib/api";
import { StaleResourceCache } from "@/lib/cache/staleResource";
import { CONTEXT_REFRESH_STALE_MS } from "@/lib/cache/contextRefresh";
import {
  countUnseenUrgentReminders,
  listUrgentReminderIds,
} from "@/lib/todos/reminderBadge";
import {
  loadHomeNudgeState,
  markHomeOverduePresented as persistHomeOverduePresented,
  pruneHomeNudgeState,
  saveHomeNudgeState,
} from "@/lib/homeReminderNudges";
import {
  loadSeenReminderIds,
  markReminderIdsSeen,
  pruneSeenReminderIds,
  saveSeenReminderIds,
} from "@/lib/reminderSeen";
import { applyRecurrenceAdvances } from "@/lib/todos/recurrence";
import { syncTodoReminders } from "@/lib/todos/todoReminders";

type TodosContextValue = {
  todos: Todo[];
  loading: boolean;
  error: boolean;
  refresh: (opts?: { silent?: boolean; force?: boolean }) => Promise<void>;
  setTodos: Dispatch<SetStateAction<Todo[]>>;
  unseenCount: number;
  showIndicator: boolean;
  /** False while todos/seen state is refreshing — avoids sub-frame urgent UI flashes. */
  remindersReady: boolean;
  seenReminderIds: Set<string>;
  homeNudgeDismissed: Set<string>;
  homeOverduePresented: Set<string>;
  markSeen: () => Promise<void>;
  dismissReminderNudge: (todoId: string) => Promise<void>;
  markHomeOverduePresented: (todoIds: string[]) => Promise<void>;
};

const TodosContext = createContext<TodosContextValue | null>(null);

export function TodosProvider({ children }: { children: ReactNode }) {
  const auth = useAuthOptional();
  const token = auth?.token;
  const userId = auth?.user?.id;
  const leadMinutes = auth?.user?.reminder_lead_minutes ?? undefined;
  const [todos, setTodos] = useState<Todo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [unseenCount, setUnseenCount] = useState(0);
  const [remindersReady, setRemindersReady] = useState(false);
  const [seenReminderIds, setSeenReminderIds] = useState<Set<string>>(new Set());
  const [homeNudgeDismissed, setHomeNudgeDismissed] = useState<Set<string>>(
    () => new Set(),
  );
  const [homeOverduePresented, setHomeOverduePresented] = useState<Set<string>>(
    () => new Set(),
  );
  const resourceRef = useRef(
    new StaleResourceCache<string, Todo[]>(CONTEXT_REFRESH_STALE_MS),
  );
  const todosRef = useRef(todos);
  todosRef.current = todos;

  const applyBadge = useCallback(
    async (items: Todo[]) => {
      if (!userId) {
        setUnseenCount(0);
        setSeenReminderIds(new Set());
        setHomeNudgeDismissed(new Set());
        setHomeOverduePresented(new Set());
        return;
      }
      const openIds = items.filter((todo) => !todo.checked).map((todo) => todo.id);
      let seen = await loadSeenReminderIds(userId);
      const pruned = pruneSeenReminderIds(seen, openIds);
      if (pruned.size !== seen.size) {
        await saveSeenReminderIds(userId, pruned);
      }
      seen = pruned;
      setSeenReminderIds(seen);
      setUnseenCount(countUnseenUrgentReminders(items, seen, undefined, leadMinutes));

      let nudges = await loadHomeNudgeState(userId);
      const prunedNudges = pruneHomeNudgeState(nudges, openIds);
      if (
        prunedNudges.dismissed.size !== nudges.dismissed.size ||
        prunedNudges.overduePresented.size !== nudges.overduePresented.size
      ) {
        await saveHomeNudgeState(userId, prunedNudges);
      }
      nudges = prunedNudges;
      setHomeNudgeDismissed(nudges.dismissed);
      setHomeOverduePresented(nudges.overduePresented);
    },
    [userId, leadMinutes],
  );

  const refresh = useCallback(
    async (opts?: { silent?: boolean; force?: boolean }) => {
      if (!token) {
        setTodos([]);
        setLoading(false);
        setUnseenCount(0);
        setRemindersReady(false);
        setSeenReminderIds(new Set());
        setHomeNudgeDismissed(new Set());
        setHomeOverduePresented(new Set());
        resourceRef.current.clear();
        return;
      }
      if (
        !opts?.force &&
        todosRef.current.length > 0 &&
        resourceRef.current.isFresh(token)
      ) {
        return;
      }
      if (!opts?.silent) {
        setLoading(true);
      }
      setError(false);

      // Only blank urgents on a cold load — silent refresh keeps the last
      // good list until the new one arrives (avoids mid-refresh flicker).
      const hadTodos = todosRef.current.length > 0;
      if (!hadTodos) setRemindersReady(false);
      try {
        const items = await resourceRef.current.fetch(
          token,
          async () => {
            const next = await api.listTodos(token);
            const advanced = applyRecurrenceAdvances(next);
            const items = advanced.todos as Todo[];
            for (const index of advanced.changedIndexes) {
              const todo = items[index];
              if (todo.id.startsWith("local-")) continue;
              void api.updateTodo(token, todo.id, { due_at: todo.due_at });
            }
            await applyBadge(items);
            void syncTodoReminders(items);
            return items;
          },
          { force: opts?.force || !hadTodos },
        );
          setTodos(items);
      } catch {
        setError(true);
      } finally {
        if (!opts?.silent) setLoading(false);
        setRemindersReady(true);
      }
    },
    [applyBadge, token],
  );

  const markSeen = useCallback(async () => {
    if (!userId || !token) {
      setUnseenCount(0);
      return;
    }
    try {
      const urgentIds = listUrgentReminderIds(todosRef.current);
      if (urgentIds.length === 0) {
        setUnseenCount(0);
        return;
      }
      await markReminderIdsSeen(userId, urgentIds);
      setSeenReminderIds((prev) => new Set([...prev, ...urgentIds]));
      setUnseenCount(0);
    } catch {
      /* keep last count */
    }
  }, [token, userId]);

  const dismissReminderNudge = useCallback(
    async (todoId: string) => {
      if (!userId) return;
      setHomeNudgeDismissed((prev) => new Set(prev).add(todoId));
      try {
        const nudges = await loadHomeNudgeState(userId);
        nudges.dismissed.add(todoId);
        await saveHomeNudgeState(userId, nudges);
        setHomeNudgeDismissed(nudges.dismissed);
        setHomeOverduePresented(nudges.overduePresented);
        await markReminderIdsSeen(userId, [todoId]);
        const seen = await loadSeenReminderIds(userId);
        setSeenReminderIds(seen);
        setUnseenCount(countUnseenUrgentReminders(todosRef.current, seen, undefined, leadMinutes));
      } catch {
        /* keep optimistic dismiss */
      }
    },
    [userId, leadMinutes],
  );

  const markHomeOverduePresented = useCallback(
    async (todoIds: string[]) => {
      if (!userId || todoIds.length === 0) return;
      try {
        const nudges = await persistHomeOverduePresented(userId, todoIds);
        setHomeOverduePresented(nudges.overduePresented);
        setHomeNudgeDismissed(nudges.dismissed);
      } catch {
        /* keep last state */
      }
    },
    [userId],
  );

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Focus refresh lives on the Lists screen — do not refetch from this
  // app-wide provider on every route change.
  useEffect(() => {
    if (!token) return;
    const onAppState = (state: AppStateStatus) => {
      if (state === "active") void refresh({ silent: true });
    };
    const sub = AppState.addEventListener("change", onAppState);
    return () => sub.remove();
  }, [refresh, token]);

  const value = useMemo<TodosContextValue>(
    () => ({
      todos,
      loading,
      error,
      refresh,
      setTodos,
      unseenCount,
      showIndicator: unseenCount > 0,
      remindersReady,
      seenReminderIds,
      homeNudgeDismissed,
      homeOverduePresented,
      markSeen,
      dismissReminderNudge,
      markHomeOverduePresented,
    }),
    [
      todos,
      loading,
      error,
      refresh,
      unseenCount,
      remindersReady,
      seenReminderIds,
      homeNudgeDismissed,
      homeOverduePresented,
      markSeen,
      dismissReminderNudge,
      markHomeOverduePresented,
    ],
  );

  return (
    <TodosContext.Provider value={value}>{children}</TodosContext.Provider>
  );
}

export function useTodos() {
  const ctx = useContext(TodosContext);
  if (!ctx) {
    throw new Error("useTodos must be used within TodosProvider");
  }
  return ctx;
}

export function useTodosOptional() {
  return useContext(TodosContext);
}
