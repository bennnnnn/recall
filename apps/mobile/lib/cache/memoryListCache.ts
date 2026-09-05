import { api, type Memory } from "@/lib/api";
import { getSessionGeneration, requireTokenSession } from "@/lib/auth";
import { isContextFresh } from "@/lib/cache/contextRefresh";

type MemoryUpdate = (current: Memory[]) => Memory[];
type CacheState = {
  session: number;
  data?: Memory[];
  fetchedAt?: number;
  pending?: { task: Promise<Memory[] | null>; updates: MemoryUpdate[] };
};

let cache: CacheState = { session: -1 };
const listeners = new Set<() => void>();

function notify(): void {
  listeners.forEach((listener) => listener());
}

export function subscribeMemoriesCache(listener: () => void): () => void {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}

function currentCache(): CacheState {
  // Reads can run during React render; silently drop the previous account here.
  if (cache.session !== getSessionGeneration()) cache = { session: getSessionGeneration() };
  return cache;
}

export function getCachedMemories(): Memory[] | undefined {
  return currentCache().data;
}

export function isMemoriesFresh(): boolean {
  const state = currentCache();
  return state.data != null && isContextFresh(state.fetchedAt);
}

export function setMemoriesCache(data: Memory[], expectedSession?: number): void {
  const state = currentCache();
  if (expectedSession != null && state.session !== expectedSession) return;
  state.data = data;
  state.fetchedAt = Date.now();
  state.pending?.updates.push(() => data);
  notify();
}

/** Apply a pure row update now and replay it over any already-running list read. */
export function updateMemoriesCache(update: MemoryUpdate, expectedSession?: number): Memory[] {
  const state = currentCache();
  if (expectedSession != null && state.session !== expectedSession) return [];
  state.data = update(state.data ?? []);
  state.pending?.updates.push(update);
  notify();
  return state.data;
}

export function invalidateMemoriesCache(): void {
  // Replace ownership so an older read cannot repopulate this session's cache.
  cache = { session: getSessionGeneration() };
  notify();
}

export async function fetchMemories(
  token: string,
  opts?: { force?: boolean; afterPending?: boolean },
): Promise<Memory[] | null> {
  try { requireTokenSession(token); } catch { return null; }
  const state = currentCache();
  if (opts?.afterPending && state.pending) {
    // Mutation recovery must not reuse a read carrying its optimistic rollback.
    // Keep this cache owner across the await so an account switch cannot start
    // a new request with the old token or overwrite the next account's rows.
    await state.pending.task;
    if (currentCache() !== state) return null;
    return fetchMemories(token, { force: true });
  }
  if (!opts?.force && !opts?.afterPending && isMemoriesFresh()) return state.data!;
  if (state.pending) return state.pending.task;
  const updates: MemoryUpdate[] = [];
  const task = (async () => {
    try {
      const data = await api.listMemories(token);
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

/** Warm the list so /memory can paint without a skeleton. */
export function prefetchMemories(token: string): void {
  void fetchMemories(token);
}
