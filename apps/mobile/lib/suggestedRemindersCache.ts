import { api, type SuggestedReminder } from "@/lib/api";
import { CONTEXT_REFRESH_STALE_MS } from "@/lib/contextRefresh";

type SuggestedRemindersPayload = {
  reminders: SuggestedReminder[];
  pending_count: number;
};

type CacheEntry = {
  data: SuggestedRemindersPayload;
  fetchedAt: number;
};

let cache: CacheEntry | null = null;
let inflight: Promise<SuggestedRemindersPayload | null> | null = null;

export function getCachedSuggestedReminders(): SuggestedRemindersPayload | undefined {
  return cache?.data;
}

export function isSuggestedRemindersFresh(): boolean {
  if (!cache) return false;
  return Date.now() - cache.fetchedAt < CONTEXT_REFRESH_STALE_MS;
}

export function setSuggestedRemindersCache(data: SuggestedRemindersPayload): void {
  cache = { data, fetchedAt: Date.now() };
}

export function invalidateSuggestedRemindersCache(): void {
  cache = null;
  inflight = null;
}

export function removeSuggestedReminderFromCache(id: string): void {
  if (!cache) return;
  const reminders = cache.data.reminders.filter((item) => item.id !== id);
  cache = {
    data: {
      reminders,
      pending_count: Math.max(0, cache.data.pending_count - 1),
    },
    fetchedAt: cache.fetchedAt,
  };
}

export async function fetchSuggestedReminders(
  token: string,
  opts?: { force?: boolean },
): Promise<SuggestedRemindersPayload | null> {
  if (!opts?.force && isSuggestedRemindersFresh()) {
    return cache!.data;
  }

  if (inflight) return inflight;

  const task = (async () => {
    try {
      const data = await api.listSuggestedReminders(token);
      setSuggestedRemindersCache(data);
      return data;
    } catch {
      return null;
    } finally {
      inflight = null;
    }
  })();

  inflight = task;
  return task;
}
