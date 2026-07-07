import { api, type ProjectDetail } from "@/lib/api";
import { CONTEXT_REFRESH_STALE_MS } from "@/lib/contextRefresh";

type CacheEntry = {
  data: ProjectDetail;
  fetchedAt: number;
};

const cache = new Map<string, CacheEntry>();
const inflight = new Map<string, Promise<ProjectDetail | null>>();

export function getCachedProjectDetail(id: string): ProjectDetail | undefined {
  return cache.get(id)?.data;
}

export function isProjectDetailFresh(id: string): boolean {
  const entry = cache.get(id);
  if (!entry) return false;
  return Date.now() - entry.fetchedAt < CONTEXT_REFRESH_STALE_MS;
}

export function setProjectDetailCache(id: string, data: ProjectDetail): void {
  cache.set(id, { data, fetchedAt: Date.now() });
}

export function invalidateProjectDetail(id: string): void {
  cache.delete(id);
  inflight.delete(id);
}

export async function fetchProjectDetail(
  token: string,
  id: string,
  opts?: { force?: boolean },
): Promise<ProjectDetail | null> {
  if (!opts?.force && isProjectDetailFresh(id)) {
    return cache.get(id)!.data;
  }

  const pending = inflight.get(id);
  if (pending) return pending;

  const task = (async () => {
    try {
      const data = await api.getProject(token, id);
      setProjectDetailCache(id, data);
      return data;
    } catch {
      return null;
    } finally {
      inflight.delete(id);
    }
  })();

  inflight.set(id, task);
  return task;
}

export function prefetchProjectDetail(token: string, id: string): void {
  if (isProjectDetailFresh(id) || inflight.has(id)) return;
  void fetchProjectDetail(token, id);
}

export function prefetchProjectDetails(token: string, ids: string[]): void {
  for (const id of ids) {
    prefetchProjectDetail(token, id);
  }
}
