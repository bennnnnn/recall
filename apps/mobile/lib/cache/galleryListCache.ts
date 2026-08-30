import { api, type AttachmentListItem } from "@/lib/api";
import { StaleResourceCache } from "@/lib/cache/staleResource";
import { CONTEXT_REFRESH_STALE_MS } from "@/lib/cache/contextRefresh";
import {
  GALLERY_PAGE_SIZE,
  galleryListCacheKey,
  galleryListParams,
  mergeGalleryItems,
  type GalleryFilter,
} from "@/lib/gallery";

export type GalleryPage = {
  items: AttachmentListItem[];
  hasMore: boolean;
};

const resource = new StaleResourceCache<string, GalleryPage>(CONTEXT_REFRESH_STALE_MS);

export function getCachedGalleryPage(
  filter: GalleryFilter,
  query: string,
): GalleryPage | undefined {
  return resource.get(galleryListCacheKey(filter, query));
}

export function isGalleryPageFresh(filter: GalleryFilter, query: string): boolean {
  return resource.isFresh(galleryListCacheKey(filter, query));
}

export function setGalleryPage(
  filter: GalleryFilter,
  query: string,
  page: GalleryPage,
): void {
  resource.set(galleryListCacheKey(filter, query), page);
}

export function invalidateGalleryCache(): void {
  resource.clear();
}

export function removeCachedGalleryItem(id: string): void {
  resource.updateEach((page) => ({
    ...page,
    items: page.items.filter((item) => item.id !== id),
  }));
}

async function loadFirstPage(
  token: string,
  filter: GalleryFilter,
  query: string,
): Promise<GalleryPage> {
  const response = await api.listAttachments(token, {
    ...galleryListParams(filter),
    ...(query ? { q: query } : {}),
    limit: GALLERY_PAGE_SIZE,
    offset: 0,
  });
  return { items: response.items, hasMore: response.has_more };
}

export async function fetchGalleryPage(
  token: string,
  filter: GalleryFilter,
  query: string,
  opts?: { force?: boolean },
): Promise<GalleryPage | null> {
  try {
    return await resource.fetch(
      galleryListCacheKey(filter, query),
      () => loadFirstPage(token, filter, query),
      opts,
    );
  } catch {
    return null;
  }
}

export async function fetchGalleryNextPage(
  token: string,
  filter: GalleryFilter,
  query: string,
): Promise<GalleryPage | null> {
  const key = galleryListCacheKey(filter, query);
  const current = resource.get(key);
  try {
    const response = await api.listAttachments(token, {
      ...galleryListParams(filter),
      ...(query ? { q: query } : {}),
      limit: GALLERY_PAGE_SIZE,
      offset: current?.items.length ?? 0,
    });
    const items = mergeGalleryItems(current?.items ?? [], response.items, false);
    return resource.set(key, { items, hasMore: response.has_more });
  } catch {
    return null;
  }
}

/** Warm All so Library can paint without a skeleton. */
export function prefetchGallery(token: string): void {
  resource.prefetch(galleryListCacheKey("all", ""), () => loadFirstPage(token, "all", ""));
}
