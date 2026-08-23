import { api, type SuggestedReminder } from "@/lib/api";
import { StaleResourceCache } from "@/lib/cache/staleResource";
import { CONTEXT_REFRESH_STALE_MS } from "@/lib/cache/contextRefresh";

type SuggestedRemindersPayload = {
  reminders: SuggestedReminder[];
  pending_count: number;
};

const SUGGESTED_REMINDERS_KEY = "suggested-reminders";
const resource = new StaleResourceCache<string, SuggestedRemindersPayload>(
  CONTEXT_REFRESH_STALE_MS,
);

export function getCachedSuggestedReminders(): SuggestedRemindersPayload | undefined {
  return resource.get(SUGGESTED_REMINDERS_KEY);
}

export function isSuggestedRemindersFresh(): boolean {
  return resource.isFresh(SUGGESTED_REMINDERS_KEY);
}

export function setSuggestedRemindersCache(data: SuggestedRemindersPayload): void {
  resource.set(SUGGESTED_REMINDERS_KEY, data);
}

export function invalidateSuggestedRemindersCache(): void {
  resource.invalidate(SUGGESTED_REMINDERS_KEY);
}

export function removeSuggestedReminderFromCache(id: string): void {
  const current = resource.get(SUGGESTED_REMINDERS_KEY);
  if (!current) return;
  resource.update(SUGGESTED_REMINDERS_KEY, () => {
    const reminders = current.reminders.filter((item) => item.id !== id);
    return {
      reminders,
      pending_count: Math.max(0, current.pending_count - 1),
    };
  });
}

/** Put a dismissed/added suggestion back when the API call fails. */
export function restoreSuggestedReminderToCache(reminder: SuggestedReminder): void {
  const current = resource.get(SUGGESTED_REMINDERS_KEY);
  if (!current) return;
  if (current.reminders.some((item) => item.id === reminder.id)) return;
  resource.update(SUGGESTED_REMINDERS_KEY, () => ({
    reminders: [reminder, ...current.reminders],
    pending_count: current.pending_count + 1,
  }));
}

export async function fetchSuggestedReminders(
  token: string,
  opts?: { force?: boolean },
): Promise<SuggestedRemindersPayload | null> {
  try {
    return await resource.fetch(
      SUGGESTED_REMINDERS_KEY,
      () => api.listSuggestedReminders(token),
      opts,
    );
  } catch {
    return null;
  }
}
