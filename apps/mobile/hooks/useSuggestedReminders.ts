import { useCallback, useState } from "react";
import { useFocusEffect } from "expo-router";

import { api, type SuggestedReminder } from "@/lib/api";
import {
  fetchSuggestedReminders,
  getCachedSuggestedReminders,
  removeSuggestedReminderFromCache,
} from "@/lib/cache/suggestedRemindersCache";

export function useSuggestedReminders(
  token: string | null,
  callbacks?: { onAdded?: () => void; onDismiss?: (id: string) => void },
) {
  const [reminders, setReminders] = useState<SuggestedReminder[]>(
    () => getCachedSuggestedReminders()?.reminders.slice(0, 3) ?? [],
  );
  const [busyId, setBusyId] = useState<string | null>(null);

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
    if (!token || busyId) return false;
    setBusyId(id);
    try {
      if (action === "add") await api.addSuggestedReminder(token, id);
      else await api.dismissSuggestedReminder(token, id);
      removeSuggestedReminderFromCache(id);
      setReminders((current) => current.filter((reminder) => reminder.id !== id));
      if (action === "add") callbacks?.onAdded?.();
      else callbacks?.onDismiss?.(id);
      return true;
    } catch {
      return false;
    } finally {
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
