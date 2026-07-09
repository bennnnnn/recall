import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type Dispatch,
  type ReactNode,
  type SetStateAction,
} from "react";
import { AppState, type AppStateStatus } from "react-native";
import { useFocusEffect } from "expo-router";

import { useAuthOptional } from "@/contexts/AuthContext";
import { api, type Todo } from "@/lib/api";
import { CONTEXT_REFRESH_STALE_MS } from "@/lib/contextRefresh";
import {
  countUnseenUrgentReminders,
  listUrgentReminderIds,
} from "@/lib/reminderBadge";
import {
  loadSeenReminderIds,
  markReminderIdsSeen,
  pruneSeenReminderIds,
  saveSeenReminderIds,
} from "@/lib/reminderSeen";
import { syncTodoReminders } from "@/lib/todoReminders";

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
  markSeen: () => Promise<void>;
  dismissReminderNudge: (todoId: string) => Promise<void>;
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
  const inflightRef = useRef<Promise<void> | null>(null);
  const todosRef = useRef(todos);
  const lastFetchedRef = useRef(0);
  todosRef.current = todos;

  const applyBadge = useCallback(
    async (items: Todo[]) => {
      if (!userId) {
        setUnseenCount(0);
        setSeenReminderIds(new Set());
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
        lastFetchedRef.current = 0;
        return;
      }
      if (
        !opts?.force &&
        todosRef.current.length > 0 &&
        Date.now() - lastFetchedRef.current < CONTEXT_REFRESH_STALE_MS
      ) {
        return;
      }
      if (inflightRef.current) {
        await inflightRef.current;
        return;
      }
      if (!opts?.silent) {
        setLoading(true);
      }
      setError(false);

      const task = (async () => {
        setRemindersReady(false);
        try {
          const items = await api.listTodos(token);
          setTodos(items);
          await applyBadge(items);
          void syncTodoReminders(items);
          lastFetchedRef.current = Date.now();
        } catch {
          setError(true);
        } finally {
          if (!opts?.silent) {
            setLoading(false);
          }
          setRemindersReady(true);
        }
      })();

      inflightRef.current = task;
      try {
        await task;
      } finally {
        inflightRef.current = null;
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
      try {
        await markReminderIdsSeen(userId, [todoId]);
        const seen = await loadSeenReminderIds(userId);
        setSeenReminderIds(seen);
        setUnseenCount(countUnseenUrgentReminders(todosRef.current, seen, undefined, leadMinutes));
      } catch {
        /* keep last state */
      }
    },
    [userId],
  );

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useFocusEffect(
    useCallback(() => {
      void refresh({ silent: true });
    }, [refresh]),
  );

  useEffect(() => {
    if (!token) return;
    const onAppState = (state: AppStateStatus) => {
      if (state === "active") void refresh({ silent: true });
    };
    const sub = AppState.addEventListener("change", onAppState);
    return () => sub.remove();
  }, [refresh, token]);

  const value: TodosContextValue = {
    todos,
    loading,
    error,
    refresh,
    setTodos,
    unseenCount,
    showIndicator: unseenCount > 0,
    remindersReady,
    seenReminderIds,
    markSeen,
    dismissReminderNudge,
  };

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
