import { api, type AttachmentListItem } from "@/lib/api";
import { getSessionGeneration } from "@/lib/auth";
import { CONTEXT_REFRESH_STALE_MS } from "@/lib/cache/contextRefresh";
import { GALLERY_PAGE_SIZE, galleryListCacheKey, galleryListParams, mergeGalleryItems, type GalleryFilter } from "@/lib/gallery";

export type GalleryPage = { items: AttachmentListItem[]; hasMore: boolean };
type Entry = {
  page?: GalleryPage;
  fetchedAt: number;
  nextOffset: number;
  revision: number;
  first?: Promise<GalleryPage | null>;
  next?: Promise<GalleryPage | null>;
};
function newCache() {
  return { session: getSessionGeneration(), entries: new Map<string, Entry>(), removed: new Set<string>() };
}
let cache = newCache();
function currentCache() {
  if (cache.session !== getSessionGeneration()) cache = newCache();
  return cache;
}
function getEntry(filter: GalleryFilter, query: string): Entry {
  const state = currentCache();
  const key = galleryListCacheKey(filter, query);
  let entry = state.entries.get(key);
  if (!entry) {
    entry = { fetchedAt: 0, nextOffset: 0, revision: 0 };
    state.entries.set(key, entry);
  }
  return entry;
}
export function getCachedGalleryPage(filter: GalleryFilter, query: string): GalleryPage | undefined {
  return getEntry(filter, query).page;
}
export function isGalleryPageFresh(filter: GalleryFilter, query: string): boolean {
  const entry = getEntry(filter, query);
  return Boolean(entry.page && Date.now() - entry.fetchedAt < CONTEXT_REFRESH_STALE_MS);
}
export function setGalleryPage(filter: GalleryFilter, query: string, page: GalleryPage): void {
  const entry = getEntry(filter, query);
  entry.revision++;
  entry.page = page;
  entry.fetchedAt = Date.now();
  entry.nextOffset = page.items.length;
  entry.first = undefined;
  entry.next = undefined;
}
export function invalidateGalleryCache(): void {
  // Replace the owner so an already-running request cannot refill a cleared cache.
  cache = newCache();
}
export function removeCachedGalleryItem(id: string): void {
  const state = currentCache();
  state.removed.add(id);
  for (const entry of state.entries.values()) {
    if (!entry.page) continue;
    const items = entry.page.items.filter((item) => item.id !== id);
    entry.nextOffset = Math.max(0, entry.nextOffset - (entry.page.items.length - items.length));
    entry.page = { ...entry.page, items };
  }
}
export async function fetchGalleryPage(
  token: string, filter: GalleryFilter, query: string, opts?: { force?: boolean },
): Promise<GalleryPage | null> {
  const state = currentCache();
  const entry = getEntry(filter, query);
  if (!opts?.force && isGalleryPageFresh(filter, query)) return entry.page!;
  if (!opts?.force && entry.first) return entry.first;
  const revision = ++entry.revision;
  entry.next = undefined;
  const task = (async () => {
    try {
      const response = await api.listAttachments(token, {
        ...galleryListParams(filter), ...(query ? { q: query } : {}), limit: GALLERY_PAGE_SIZE, offset: 0,
      });
      if (currentCache() !== state || revision !== entry.revision) return null;
      const items = response.items.filter((row) => !state.removed.has(row.id));
      entry.page = { items, hasMore: response.has_more };
      entry.nextOffset = items.length;
      entry.fetchedAt = Date.now();
      return entry.page;
    } catch {
      return null;
    }
  })();
  entry.first = task;
  try { return await task; }
  finally { if (entry.first === task) entry.first = undefined; }
}
export async function fetchGalleryNextPage(token: string, filter: GalleryFilter, query: string): Promise<GalleryPage | null> {
  const state = currentCache();
  const entry = getEntry(filter, query);
  if (entry.first) return entry.first;
  if (!entry.page) return fetchGalleryPage(token, filter, query);
  if (!entry.page.hasMore) return entry.page;
  if (entry.next) return entry.next;
  const revision = entry.revision;
  const task = (async () => {
    try {
      while (true) {
        const offset = entry.nextOffset;
        const response = await api.listAttachments(token, {
          ...galleryListParams(filter), ...(query ? { q: query } : {}), limit: GALLERY_PAGE_SIZE, offset,
        });
        if (currentCache() !== state || revision !== entry.revision) return null;
        // A confirmed deletion can shift the server's rows before this query
        // runs. Fetch the corrected offset so the file at that boundary is not skipped.
        if (offset !== entry.nextOffset) continue;
        const incoming = response.items.filter((row) => !state.removed.has(row.id));
        entry.page = { items: mergeGalleryItems(entry.page?.items ?? [], incoming, false), hasMore: response.has_more };
        // Track consumed rows, including duplicate rows from a shifting offset page.
        entry.nextOffset += incoming.length;
        return entry.page;
      }
    } catch {
      return null;
    }
  })();
  entry.next = task;
  try { return await task; }
  finally { if (entry.next === task) entry.next = undefined; }
}
/** Warm All so Library can paint without a skeleton. */
export function prefetchGallery(token: string): void {
  void fetchGalleryPage(token, "all", "");
}
