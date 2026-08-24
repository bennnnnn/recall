import { api, type Usage } from "@/lib/api";
import { CONTEXT_REFRESH_STALE_MS } from "@/lib/cache/contextRefresh";
import { StaleResourceCache } from "@/lib/cache/staleResource";

const resource = new StaleResourceCache<string, Usage>(CONTEXT_REFRESH_STALE_MS);

export function getCachedUsage(token: string): Usage | undefined {
  return resource.get(token);
}

export function invalidateUsageCache(): void {
  resource.clear();
}

export async function fetchTodayUsage(
  token: string,
  opts?: { force?: boolean },
): Promise<Usage | null> {
  try {
    return await resource.fetch(token, () => api.todayUsage(token), opts);
  } catch {
    return null;
  }
}
