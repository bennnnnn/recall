import { api, type SuggestedReminder } from "@/lib/api";
import { getSessionGeneration, requireTokenSession } from "@/lib/auth";
import { isContextFresh } from "@/lib/cache/contextRefresh";

type SuggestedRemindersPayload = {
  reminders: SuggestedReminder[];
  pending_count: number;
};
type Update = (current: SuggestedRemindersPayload) => SuggestedRemindersPayload;
type CacheState = {
  session: number;
  data?: SuggestedRemindersPayload;
  fetchedAt?: number;
  pending?: { task: Promise<SuggestedRemindersPayload | null>; updates: Update[] };
};
let cache: CacheState = { session: -1 };
const listeners = new Set<() => void>();
function notify(): void { listeners.forEach((listener) => listener()); }
function currentCache(): CacheState {
  if (cache.session !== getSessionGeneration()) cache = { session: getSessionGeneration() };
  return cache;
}

export function subscribeSuggestedRemindersCache(listener: () => void): () => void {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}

export function getCachedSuggestedReminders(): SuggestedRemindersPayload | undefined {
  return currentCache().data;
}

export function isSuggestedRemindersFresh(): boolean {
  const state = currentCache();
  return state.data != null && isContextFresh(state.fetchedAt);
}

export function setSuggestedRemindersCache(data: SuggestedRemindersPayload, expectedSession?: number): void {
  const state = currentCache();
  if (expectedSession != null && state.session !== expectedSession) return;
  state.data = data;
  state.fetchedAt = Date.now();
  state.pending?.updates.push(() => data);
  notify();
}

export function invalidateSuggestedRemindersCache(): void {
  cache = { session: getSessionGeneration() };
  notify();
}

function updateCache(update: Update, expectedSession?: number): boolean {
  const state = currentCache();
  if (expectedSession != null && state.session !== expectedSession) return false;
  if (state.data) state.data = update(state.data);
  state.pending?.updates.push(update);
  notify();
  return true;
}

export function removeSuggestedReminderFromCache(id: string, expectedSession?: number): void {
  updateCache((current) => {
    if (!current.reminders.some((item) => item.id === id)) return current;
    return {
      reminders: current.reminders.filter((item) => item.id !== id),
      pending_count: Math.max(0, current.pending_count - 1),
    };
  }, expectedSession);
}

/** Put a dismissed/added suggestion back when the API call fails. */
export function restoreSuggestedReminderToCache(reminder: SuggestedReminder, expectedSession?: number): void {
  updateCache((current) => current.reminders.some((item) => item.id === reminder.id) ? current : ({
    reminders: [reminder, ...current.reminders],
    pending_count: current.pending_count + 1,
  }), expectedSession);
}

type ReminderListSetter = (updater: (prev: SuggestedReminder[]) => SuggestedReminder[]) => void;

/** Drop from cache + UI together (optimistic add/dismiss). */
export function dropSuggestedReminder(id: string, setReminders: ReminderListSetter, expectedSession?: number): void {
  if (expectedSession != null && expectedSession !== getSessionGeneration()) return;
  removeSuggestedReminderFromCache(id, expectedSession);
  setReminders((prev) => prev.filter((item) => item.id !== id));
}

/** Restore cache + UI together after a failed add/dismiss. */
export function undeleteSuggestedReminder(reminder: SuggestedReminder, setReminders: ReminderListSetter, expectedSession?: number): void {
  if (expectedSession != null && expectedSession !== getSessionGeneration()) return;
  restoreSuggestedReminderToCache(reminder, expectedSession);
  setReminders((prev) => prev.some((item) => item.id === reminder.id) ? prev : [reminder, ...prev]);
}

export async function fetchSuggestedReminders(
  token: string,
  opts?: { force?: boolean; afterPending?: boolean },
): Promise<SuggestedRemindersPayload | null> {
  try { requireTokenSession(token); } catch { return null; }
  const state = currentCache();
  if (opts?.afterPending && state.pending) {
    await state.pending.task;
    if (currentCache() !== state) return null;
    return fetchSuggestedReminders(token, { force: true });
  }
  if (!opts?.force && !opts?.afterPending && isSuggestedRemindersFresh()) return state.data!;
  if (state.pending) return state.pending.task;
  const updates: Update[] = [];
  const task = (async () => {
    try {
      const data = await api.listSuggestedReminders(token);
      if (currentCache() !== state) return null;
      state.data = updates.reduce((rows, update) => update(rows), data);
      state.fetchedAt = Date.now();
      notify();
      return state.data;
    } catch {
      return null;
    }
  })();
  const pending = { task, updates };
  state.pending = pending;
  try { return await task; }
  finally { if (state.pending === pending) state.pending = undefined; }
}
