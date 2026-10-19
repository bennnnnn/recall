import { api, type AttachmentListItem } from "@/lib/api";
import { CONTEXT_REFRESH_STALE_MS } from "@/lib/cache/contextRefresh";
import { asError, SessionResourceCache, sessionChanged, type ResourceResult } from "@/lib/cache/sessionResource";
import { GALLERY_PAGE_SIZE, galleryListCacheKey, galleryListParams, mergeGalleryItems, type GalleryFilter } from "@/features/attachments/model/gallery";

export type GalleryPage = { items: AttachmentListItem[]; hasMore: boolean };
/** The rows shown, how many server rows they consumed, and which first page they grew from. */
type GalleryEntry = { page: GalleryPage; nextOffset: number; lineage: number };
type NextPageRead = { lineage: number; task: Promise<ResourceResult<GalleryPage>> };
type GallerySession = {
  /** Deleted this session; an earlier read must not bring them back. */
  removed: Set<string>;
  next: Map<string, NextPageRead>;
  lineages: number;
};
type ListResponse = { items: AttachmentListItem[]; has_more: boolean };
/** One entry per filter and search; typing a search must not keep every query forever. */
const MAX_GALLERY_QUERIES = 20;

const resource = new SessionResourceCache<string, GalleryEntry, GallerySession>({
  staleMs: CONTEXT_REFRESH_STALE_MS,
  maxEntries: MAX_GALLERY_QUERIES,
  sessionState: () => ({ removed: new Set(), next: new Map(), lineages: 0 }),
});

function firstEntry(page: GalleryPage): GalleryEntry {
  return { page, nextOffset: page.items.length, lineage: ++resource.state().lineages };
}
function keptRows(response: ListResponse): AttachmentListItem[] {
  const { removed } = resource.state();
  return response.items.filter((row) => !removed.has(row.id));
}
function readRows(token: string, filter: GalleryFilter, query: string, offset: number): Promise<ListResponse> {
  return api.listAttachments(token, {
    ...galleryListParams(filter), ...(query ? { q: query } : {}), limit: GALLERY_PAGE_SIZE, offset,
  });
}
function pageResult(result: ResourceResult<GalleryEntry>): ResourceResult<GalleryPage> {
  return result.error
    ? { data: result.data?.page ?? null, error: result.error }
    : { data: result.data.page, error: null };
}
function withoutItem(entry: GalleryEntry, id: string): GalleryEntry {
  const items = entry.page.items.filter((item) => item.id !== id);
  const dropped = entry.page.items.length - items.length;
  if (!dropped) return entry;
  return { ...entry, page: { ...entry.page, items }, nextOffset: Math.max(0, entry.nextOffset - dropped) };
}

export function getCachedGalleryPage(filter: GalleryFilter, query: string): GalleryPage | undefined {
  return resource.get(galleryListCacheKey(filter, query))?.page;
}
export function isGalleryPageFresh(filter: GalleryFilter, query: string): boolean {
  return resource.isFresh(galleryListCacheKey(filter, query));
}
export function setGalleryPage(filter: GalleryFilter, query: string, page: GalleryPage): void {
  resource.set(galleryListCacheKey(filter, query), firstEntry(page));
}
export function invalidateGalleryCache(): void {
  resource.invalidate();
}
export function removeCachedGalleryItem(id: string): void {
  resource.state().removed.add(id);
  resource.updateEach((entry) => withoutItem(entry, id));
}

export async function fetchGalleryPage(
  token: string, filter: GalleryFilter, query: string, opts?: { force?: boolean },
): Promise<ResourceResult<GalleryPage>> {
  const result = await resource.fetch(galleryListCacheKey(filter, query), token, async () => {
    const response = await readRows(token, filter, query, 0);
    return firstEntry({ items: keptRows(response), hasMore: response.has_more });
  }, opts);
  return pageResult(result);
}

export async function fetchGalleryNextPage(
  token: string, filter: GalleryFilter, query: string,
): Promise<ResourceResult<GalleryPage>> {
  const key = galleryListCacheKey(filter, query);
  const first = resource.inflight(key);
  if (first) return pageResult(await first);
  const entry = resource.get(key);
  if (!entry) return fetchGalleryPage(token, filter, query);
  if (!entry.page.hasMore) return { data: entry.page, error: null };
  const { next } = resource.state();
  const running = next.get(key);
  if (running?.lineage === entry.lineage) return running.task;
  const task = readNextPage(token, filter, query, entry.lineage);
  next.set(key, { lineage: entry.lineage, task });
  try { return await task; }
  finally { if (next.get(key)?.task === task) next.delete(key); }
}

async function readNextPage(
  token: string, filter: GalleryFilter, query: string, lineage: number,
): Promise<ResourceResult<GalleryPage>> {
  const key = galleryListCacheKey(filter, query);
  const isCurrent = resource.lease();
  // A first-page read that started or landed since makes this page's offset meaningless.
  const replaced = () => resource.inflight(key) !== undefined || resource.get(key)?.lineage !== lineage;
  try {
    while (true) {
      const offset = resource.get(key)?.nextOffset ?? 0;
      const response = await readRows(token, filter, query, offset);
      if (!isCurrent()) return sessionChanged();
      if (replaced()) return currentPage(key);
      // A confirmed deletion can shift the server's rows before this query
      // runs. Fetch the corrected offset so the file at that boundary is not skipped.
      if (offset !== resource.get(key)?.nextOffset) continue;
      const incoming = keptRows(response);
      const grown = resource.update(key, (current) => ({
        ...current,
        page: { items: mergeGalleryItems(current.page.items, incoming, false), hasMore: response.has_more },
        // Track consumed rows, including duplicate rows from a shifting offset page.
        nextOffset: current.nextOffset + incoming.length,
      }));
      return currentPage(key, grown);
    }
  } catch (caught) {
    if (!isCurrent()) return sessionChanged();
    return { data: resource.get(key)?.page ?? null, error: asError(caught) };
  }
}

async function currentPage(key: string, entry = resource.get(key)): Promise<ResourceResult<GalleryPage>> {
  const first = resource.inflight(key);
  if (first) return pageResult(await first);
  return entry
    ? { data: entry.page, error: null }
    : { data: null, error: new Error("The Library page was replaced.") };
}

/** Warm All so Library can paint without a skeleton. */
export function prefetchGallery(token: string): void {
  void fetchGalleryPage(token, "all", "");
}
