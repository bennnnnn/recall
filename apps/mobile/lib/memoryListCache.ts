import { api, type Memory } from "@/lib/api";
import { CONTEXT_REFRESH_STALE_MS } from "@/lib/contextRefresh";

type CacheEntry = {
  data: Memory[];
  fetchedAt: number;
};

let cache: CacheEntry | null = null;
let inflight: Promise<Memory[] | null> | null = null;

export function getCachedMemories(): Memory[] | undefined {
  return cache?.data;
}

export function isMemoriesFresh(): boolean {
  if (!cache) return false;
  return Date.now() - cache.fetchedAt < CONTEXT_REFRESH_STALE_MS;
}

export function setMemoriesCache(data: Memory[]): void {
  cache = { data, fetchedAt: Date.now() };
}

export function invalidateMemoriesCache(): void {
  cache = null;
  inflight = null;
}

export async function fetchMemories(
  token: string,
  opts?: { force?: boolean },
): Promise<Memory[] | null> {
  if (!opts?.force && isMemoriesFresh()) {
    return cache!.data;
  }

  if (inflight) return inflight;

  const task = (async () => {
    try {
      const data = await api.listMemories(token);
      setMemoriesCache(data);
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

/** Warm the list so /memory can paint without a skeleton. */
export function prefetchMemories(token: string): void {
  if (isMemoriesFresh() || inflight) return;
  void fetchMemories(token);
}
