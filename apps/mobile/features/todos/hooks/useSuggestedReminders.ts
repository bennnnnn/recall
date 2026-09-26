import { useCallback, useEffect, useRef, useState } from "react";
import { useFocusEffect } from "expo-router";
import { useTranslation } from "react-i18next";

import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { replaceTodoById } from "@/features/todos/model/optimisticTodo";
import { api, type SuggestedReminder, type Todo } from "@/lib/api";
import { getSessionGeneration } from "@/lib/auth";
import {
  fetchSuggestedReminders,
  getCachedSuggestedReminders,
  removeSuggestedReminderFromCache,
  restoreSuggestedReminderToCache,
  subscribeSuggestedRemindersCache,
} from "@/lib/cache/suggestedRemindersCache";
import { alertDialog } from "@/ui/overlay/dialogs";

type Params = {
  token: string | null;
  isCurrentSession: () => boolean;
  isCurrentView: () => boolean;
  setTodos: React.Dispatch<React.SetStateAction<Todo[]>>;
  refreshTodos: (opts?: { silent?: boolean; force?: boolean; afterPending?: boolean }) => Promise<void>;
};

/** Owns the focused To-do screen's Gmail suggestions and optimistic actions. */
export function useSuggestedReminders({
  token,
  isCurrentSession,
  isCurrentView,
  setTodos,
  refreshTodos,
}: Params) {
  const { t } = useTranslation();
  const feedback = useActionFeedbackOptional();
  const session = getSessionGeneration();
  const mounted = useRef(true);
  const [reminders, setReminders] = useState<SuggestedReminder[]>(
    () => getCachedSuggestedReminders()?.reminders ?? [],
  );
  const [busyIds, setBusyIds] = useState<ReadonlySet<string>>(new Set());
  const pendingIds = useRef(new Set<string>());

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  const canAct = useCallback(
    () => mounted.current && getSessionGeneration() === session && isCurrentSession() && isCurrentView(),
    [isCurrentSession, isCurrentView, session],
  );
  const publishCache = useCallback(() => {
    if (canAct()) setReminders(getCachedSuggestedReminders()?.reminders ?? []);
  }, [canAct]);

  useEffect(() => subscribeSuggestedRemindersCache(publishCache), [publishCache]);

  const load = useCallback(async () => {
    if (!token || !canAct()) return;
    const result = await fetchSuggestedReminders(token, { force: true });
    if (result && canAct()) setReminders(getCachedSuggestedReminders()?.reminders ?? result.reminders);
  }, [token, canAct]);

  useFocusEffect(useCallback(() => { void load(); }, [load]));

  const reportError = useCallback((key: string) => {
    if (!canAct()) return;
    if (feedback) feedback.error(t(key));
    else void alertDialog({ title: t("todos.error"), message: t(key) });
  }, [canAct, feedback, t]);

  const mutate = useCallback(async (reminder: SuggestedReminder, add: boolean) => {
    if (!token || !canAct() || pendingIds.current.has(reminder.id)) return;
    const snapshot = getCachedSuggestedReminders()?.reminders.find(
      (item) => item.id === reminder.id,
    ) ?? reminder;
    pendingIds.current.add(reminder.id);
    setBusyIds((current) => new Set(current).add(reminder.id));
    removeSuggestedReminderFromCache(reminder.id, session);
    try {
      const created = add
        ? await api.addSuggestedReminder(token, reminder.id)
        : await api.dismissSuggestedReminder(token, reminder.id);
      if (!canAct()) return;
      if (created) {
        setTodos((rows) => replaceTodoById(rows, created.id, created));
        void refreshTodos({ silent: true, force: true, afterPending: true });
      }
    } catch {
      if (canAct()) restoreSuggestedReminderToCache(snapshot, session);
      reportError(add ? "todos.error_create" : "common.error");
    } finally {
      pendingIds.current.delete(reminder.id);
      if (canAct()) {
        setBusyIds((current) => {
          const next = new Set(current);
          next.delete(reminder.id);
          return next;
        });
      }
    }
  }, [token, canAct, session, setTodos, refreshTodos, reportError]);

  return {
    reminders,
    busyIds,
    refresh: load,
    add: (reminder: SuggestedReminder) => void mutate(reminder, true),
    dismiss: (reminder: SuggestedReminder) => void mutate(reminder, false),
  };
}
