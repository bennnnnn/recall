import { api, type ProjectDetail } from "@/lib/api";
import { getSessionGeneration, requireTokenSession } from "@/lib/auth";
import { isContextFresh } from "@/lib/cache/contextRefresh";

type Update = (current: ProjectDetail) => ProjectDetail;
type Entry = {
  data?: ProjectDetail;
  fetchedAt?: number;
  pending?: { task: Promise<ProjectDetail | null>; updates: Update[] };
};
let session = -1;
let entries = new Map<string, Entry>();
const listeners = new Set<() => void>();
const notify = () => listeners.forEach((listener) => listener());
function currentEntries() {
  if (session !== getSessionGeneration()) {
    session = getSessionGeneration();
    entries = new Map();
  }
  return entries;
}
export function subscribeProjectDetailCache(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}
export function getCachedProjectDetail(id: string) {
  return currentEntries().get(id)?.data;
}
export function isProjectDetailFresh(id: string) {
  const entry = currentEntries().get(id);
  return entry?.data != null && isContextFresh(entry.fetchedAt);
}
export function setProjectDetailCache(
  id: string,
  data: ProjectDetail,
  expectedSession = getSessionGeneration(),
) {
  if (expectedSession !== getSessionGeneration()) return;
  currentEntries().set(id, { data, fetchedAt: Date.now() });
  notify();
}
export function updateProjectDetailCache(
  id: string,
  update: Update,
  expectedSession = getSessionGeneration(),
) {
  if (expectedSession !== getSessionGeneration()) return;
  const entry = currentEntries().get(id);
  if (!entry) return;
  if (entry.data) entry.data = update(entry.data);
  entry.pending?.updates.push(update);
  notify();
}
export function invalidateProjectDetail(id: string, expectedSession = getSessionGeneration()) {
  if (expectedSession !== getSessionGeneration()) return;
  const cache = currentEntries();
  cache.set(id, { data: cache.get(id)?.data });
  notify();
}
export async function fetchProjectDetail(
  token: string,
  id: string,
  opts?: { force?: boolean; afterPending?: boolean },
): Promise<ProjectDetail | null> {
  try {
    requireTokenSession(token);
  } catch {
    return null;
  }
  const cache = currentEntries();
  const entry = cache.get(id) ?? {};
  cache.set(id, entry);
  if (opts?.afterPending && entry.pending) {
    await entry.pending.task;
    if (currentEntries() !== cache) return null;
    return fetchProjectDetail(token, id, { force: true });
  }
  if (!opts?.force && !opts?.afterPending && isProjectDetailFresh(id)) return entry.data!;
  if (entry.pending) return entry.pending.task;
  const updates: Update[] = [];
  const task = (async () => {
    try {
      const data = await api.getProject(token, id, { includeLists: true });
      if (currentEntries() !== cache || cache.get(id) !== entry) return null;
      entry.data = updates.reduce((value, update) => update(value), data);
      entry.fetchedAt = Date.now();
      notify();
      return entry.data;
    } catch {
      return null;
    }
  })();
  const pending = { task, updates };
  entry.pending = pending;
  try {
    return await task;
  } finally {
    if (entry.pending === pending) entry.pending = undefined;
  }
}
export function prefetchProjectDetail(token: string, id: string) {
  void fetchProjectDetail(token, id);
}
