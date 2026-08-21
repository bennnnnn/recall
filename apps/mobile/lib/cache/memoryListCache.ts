import { api, type Memory } from "@/lib/api";
import { StaleResourceCache } from "@/lib/cache/staleResource";
import { CONTEXT_REFRESH_STALE_MS } from "@/lib/cache/contextRefresh";

const MEMORY_LIST_KEY = "memory-list";
const resource = new StaleResourceCache<string, Memory[]>(CONTEXT_REFRESH_STALE_MS);

export function getCachedMemories(): Memory[] | undefined {
  return resource.get(MEMORY_LIST_KEY);
}

export function isMemoriesFresh(): boolean {
  return resource.isFresh(MEMORY_LIST_KEY);
}

export function setMemoriesCache(data: Memory[]): void {
  resource.set(MEMORY_LIST_KEY, data);
}

export function invalidateMemoriesCache(): void {
  resource.invalidate(MEMORY_LIST_KEY);
}

export async function fetchMemories(
  token: string,
  opts?: { force?: boolean },
): Promise<Memory[] | null> {
  try {
    return await resource.fetch(MEMORY_LIST_KEY, () => api.listMemories(token), opts);
  } catch {
    return null;
  }
}

/** Warm the list so /memory can paint without a skeleton. */
export function prefetchMemories(token: string): void {
  resource.prefetch(MEMORY_LIST_KEY, () => api.listMemories(token));
}
