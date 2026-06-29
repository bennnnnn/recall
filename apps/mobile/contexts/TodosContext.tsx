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
  refresh: (opts?: { silent?: boolean }) => Promise<void>;
  setTodos: Dispatch<SetStateAction<Todo[]>>;
  unseenCount: number;
  showIndicator: boolean;
  markSeen: () => Promise<void>;
};

const TodosContext = createContext<TodosContextValue | null>(null);

export function TodosProvider({ children }: { children: ReactNode }) {
  const auth = useAuthOptional();
  const token = auth?.token;
  const userId = auth?.user?.id;
  const [todos, setTodos] = useState<Todo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [unseenCount, setUnseenCount] = useState(0);
  const inflightRef = useRef<Promise<void> | null>(null);
  const todosRef = useRef(todos);
  todosRef.current = todos;

  const applyBadge = useCallback(
    async (items: Todo[]) => {
      if (!userId) {
        setUnseenCount(0);
        return;
      }
      const openIds = items.filter((todo) => !todo.checked).map((todo) => todo.id);
      let seen = await loadSeenReminderIds(userId);
      const pruned = pruneSeenReminderIds(seen, openIds);
      if (pruned.size !== seen.size) {
        await saveSeenReminderIds(userId, pruned);
      }
      seen = pruned;
      setUnseenCount(countUnseenUrgentReminders(items, seen));
    },
    [userId],
  );

  const refresh = useCallback(
    async (opts?: { silent?: boolean }) => {
      if (!token) {
        setTodos([]);
        setLoading(false);
        setUnseenCount(0);
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
        try {
          const items = await api.listTodos(token);
          setTodos(items);
          await applyBadge(items);
          void syncTodoReminders(items);
        } catch {
          setError(true);
        } finally {
          if (!opts?.silent) {
            setLoading(false);
          }
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
      setUnseenCount(0);
    } catch {
      /* keep last count */
    }
  }, [token, userId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useFocusEffect(
    useCallback(() => {
      void refresh({ silent: todosRef.current.length > 0 });
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
    markSeen,
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
