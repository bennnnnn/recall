import { useCallback, useRef, useState } from "react";
import { useFocusEffect } from "expo-router";
import { useTranslation } from "react-i18next";

import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { useTodosOptional } from "@/contexts/TodosContext";
import { api, type SuggestedReminder } from "@/lib/api";
import {
  fetchSuggestedReminders,
  getCachedSuggestedReminders,
  removeSuggestedReminderFromCache,
  restoreSuggestedReminderToCache,
} from "@/lib/cache/suggestedRemindersCache";
import { syncTodoReminders } from "@/lib/todos/todoReminders";

export function useSuggestedReminders(
  token: string | null,
  callbacks?: { onAdded?: () => void; onDismiss?: (id: string) => void },
) {
  const { t } = useTranslation();
  const feedback = useActionFeedbackOptional();
  const todosCtx = useTodosOptional();
  const [reminders, setReminders] = useState<SuggestedReminder[]>(
    () => getCachedSuggestedReminders()?.reminders.slice(0, 3) ?? [],
  );
  const [busyId, setBusyId] = useState<string | null>(null);
  const busyRef = useRef<string | null>(null);

  const load = useCallback(async () => {
    if (!token) {
      setReminders([]);
      return;
    }
    const data = await fetchSuggestedReminders(token, { force: true });
    setReminders((data?.reminders ?? []).slice(0, 3));
  }, [token]);

  useFocusEffect(
    useCallback(() => {
      void load();
    }, [load]),
  );

  const mutate = async (id: string, action: "add" | "dismiss") => {
    if (!token || busyRef.current) return false;
    busyRef.current = id;
    setBusyId(id);
    const removed = reminders.find((reminder) => reminder.id === id) ?? null;
    removeSuggestedReminderFromCache(id);
    setReminders((current) => current.filter((reminder) => reminder.id !== id));
    try {
      if (action === "add") {
        const created = await api.addSuggestedReminder(token, id);
        if (todosCtx) {
          const next = [created, ...todosCtx.todos.filter((item) => item.id !== created.id)];
          todosCtx.setTodos(next);
          void syncTodoReminders(next);
        }
        callbacks?.onAdded?.();
      } else {
        await api.dismissSuggestedReminder(token, id);
        callbacks?.onDismiss?.(id);
      }
      return true;
    } catch {
      if (removed) {
        restoreSuggestedReminderToCache(removed);
        setReminders((current) =>
          current.some((reminder) => reminder.id === removed.id)
            ? current
            : [removed, ...current],
        );
      }
      feedback?.error(t("common.error"));
      return false;
    } finally {
      busyRef.current = null;
      setBusyId(null);
    }
  };

  return {
    reminders,
    busyId,
    add: (id: string) => mutate(id, "add"),
    dismiss: (id: string) => mutate(id, "dismiss"),
  };
}
