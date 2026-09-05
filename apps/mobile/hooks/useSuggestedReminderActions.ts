import { useCallback, useEffect, useMemo, useState } from "react";
import { api, type SuggestedReminder, type Todo } from "@/lib/api";
import {
  fetchSuggestedReminders, getCachedSuggestedReminders,
  removeSuggestedReminderFromCache, restoreSuggestedReminderToCache,
} from "@/lib/cache/suggestedRemindersCache";
import { replaceTodoById } from "@/lib/todos/optimisticTodo";

type MutationState = { session: number; pending: Set<string>; listeners: Set<(error?: boolean) => void> };
let state: MutationState = { session: -1, pending: new Set(), listeners: new Set() };
function sessionMutations(session: number): MutationState {
  if (state.session !== session) state = { session, pending: new Set(), listeners: new Set() };
  return state;
}
function notify(state: MutationState, error?: boolean): void {
  state.listeners.forEach((listener) => listener(error));
}

type Params = {
  token: string | null;
  session: number;
  isSameOwner: () => boolean;
  canAct: () => boolean;
  setTodos: React.Dispatch<React.SetStateAction<Todo[]>>;
  refresh: (opts?: { silent?: boolean; force?: boolean; afterPending?: boolean }) => Promise<void>;
  reportError: (key: string) => void;
  setLoadError: (error: boolean) => void;
};

/** Suggestion writes remain account-owned after a Schedule visit ends. */
export function useSuggestedReminderActions({ token, session, isSameOwner, canAct,
  setTodos, refresh, reportError, setLoadError,
}: Params) {
  const mutations = useMemo(() => sessionMutations(session), [session]);
  const [, redraw] = useState(0);
  useEffect(() => {
    const changed = (error?: boolean) => {
      if (!canAct()) return;
      redraw((value) => value + 1);
      if (error != null) setLoadError(error);
    };
    mutations.listeners.add(changed);
    return () => { mutations.listeners.delete(changed); };
  }, [mutations, canAct, setLoadError]);

  const mutate = useCallback(async (reminder: SuggestedReminder, add: boolean) => {
    if (!token || !canAct() || mutations.pending.has(reminder.id)) return;
    const snapshot = getCachedSuggestedReminders()?.reminders.find((item) => item.id === reminder.id);
    if (!snapshot) return;
    mutations.pending.add(reminder.id);
    notify(mutations);
    removeSuggestedReminderFromCache(reminder.id, session);
    try {
      const created = add ? await api.addSuggestedReminder(token, reminder.id)
        : await api.dismissSuggestedReminder(token, reminder.id);
      if (!isSameOwner()) return;
      removeSuggestedReminderFromCache(reminder.id, session);
      if (created) {
        setTodos((rows) => replaceTodoById(rows, created.id, created));
        void refresh({ silent: true, force: true, afterPending: true });
      }
    } catch {
      if (isSameOwner()) {
        restoreSuggestedReminderToCache(snapshot, session);
        void fetchSuggestedReminders(token, { force: true, afterPending: true }).then((result) => {
          if (isSameOwner()) notify(mutations, result === null);
        });
      }
      reportError(add ? "todos.error_create" : "common.error");
    } finally {
      mutations.pending.delete(reminder.id);
      notify(mutations);
    }
  }, [token, canAct, mutations, session, isSameOwner, setTodos, refresh, reportError]);
  const handleAddSuggestion = useCallback(async (reminder: SuggestedReminder) => { await mutate(reminder, true); }, [mutate]);
  const handleDismissSuggestion = useCallback(async (reminder: SuggestedReminder) => { await mutate(reminder, false); }, [mutate]);
  return { suggestionBusyId: mutations.pending.values().next().value ?? null, handleAddSuggestion, handleDismissSuggestion };
}
