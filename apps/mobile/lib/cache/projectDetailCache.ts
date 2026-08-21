import { api, type ProjectDetail } from "@/lib/api";
import { StaleResourceCache } from "@/lib/cache/staleResource";
import { CONTEXT_REFRESH_STALE_MS } from "@/lib/cache/contextRefresh";

const resource = new StaleResourceCache<string, ProjectDetail>(CONTEXT_REFRESH_STALE_MS);

export function getCachedProjectDetail(id: string): ProjectDetail | undefined {
  return resource.get(id);
}

export function isProjectDetailFresh(id: string): boolean {
  return resource.isFresh(id);
}

export function setProjectDetailCache(id: string, data: ProjectDetail): void {
  resource.set(id, data);
}

export function invalidateProjectDetail(id: string): void {
  resource.invalidate(id);
}

export async function fetchProjectDetail(
  token: string,
  id: string,
  opts?: { force?: boolean },
): Promise<ProjectDetail | null> {
  try {
    return await resource.fetch(
      id,
      () => api.getProject(token, id, { includeLists: true }),
      opts,
    );
  } catch {
    return null;
  }
}

export function prefetchProjectDetail(token: string, id: string): void {
  resource.prefetch(id, () => api.getProject(token, id, { includeLists: true }));
}

export function prefetchProjectDetails(token: string, ids: string[]): void {
  for (const id of ids) {
    prefetchProjectDetail(token, id);
  }
}
