import { useCallback, useEffect, useRef, useState } from "react";
import { useFocusEffect } from "expo-router";

import { useAuth } from "@/contexts/AuthContext";
import { type AttachmentListItem } from "@/lib/api";
import {
  fetchGalleryNextPage,
  fetchGalleryPage,
  getCachedGalleryPage,
  isGalleryPageFresh,
  removeCachedGalleryItem,
  type GalleryPage,
} from "@/lib/cache/galleryListCache";
import {
  GALLERY_SEARCH_DEBOUNCE_MS,
  galleryListCacheKey,
  type GalleryFilter,
} from "@/lib/gallery";

export type { GalleryFilter };

function pageFromCache(snapshot: GalleryPage | undefined): {
  items: AttachmentListItem[];
  hasMore: boolean;
  loading: boolean;
} {
  if (!snapshot) return { items: [], hasMore: false, loading: true };
  return { items: snapshot.items, hasMore: snapshot.hasMore, loading: false };
}

export function useGalleryData(filter: GalleryFilter, searchQuery: string) {
  const { token } = useAuth();
  const trimmedQuery = searchQuery.trim();
  const [debouncedQuery, setDebouncedQuery] = useState(trimmedQuery);
  const cacheKey = galleryListCacheKey(filter, debouncedQuery);
  const snapshot = getCachedGalleryPage(filter, debouncedQuery);
  const initial = pageFromCache(snapshot);

  const [pageKey, setPageKey] = useState(cacheKey);
  const [items, setItems] = useState<AttachmentListItem[]>(initial.items);
  const [loading, setLoading] = useState(initial.loading);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState(false);
  const [hasMore, setHasMore] = useState(initial.hasMore);
  const [pullRefreshing, setPullRefreshing] = useState(false);
  const inFlightRef = useRef(false);
  const genRef = useRef(0);

  if (pageKey !== cacheKey) {
    const next = pageFromCache(snapshot);
    setPageKey(cacheKey);
    setItems(next.items);
    setHasMore(next.hasMore);
    setLoading(next.loading);
    setError(false);
  }

  useEffect(() => {
    const handle = setTimeout(() => setDebouncedQuery(trimmedQuery), GALLERY_SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(handle);
  }, [trimmedQuery]);

  const load = useCallback(
    async (options: { reset?: boolean; silent?: boolean; force?: boolean } = {}) => {
      if (!token) return;
      const reset = options.reset ?? true;
      if (!reset && inFlightRef.current) return;

      if (reset && !options.force && isGalleryPageFresh(filter, debouncedQuery)) {
        const cached = getCachedGalleryPage(filter, debouncedQuery);
        if (cached) {
          setItems(cached.items);
          setHasMore(cached.hasMore);
          setLoading(false);
          setError(false);
          return;
        }
      }

      if (reset) genRef.current += 1;
      const gen = genRef.current;
      inFlightRef.current = true;
      const cached = getCachedGalleryPage(filter, debouncedQuery);
      if (!options.silent) {
        if (reset && !cached) setLoading(true);
        else if (!reset) setLoadingMore(true);
      }
      try {
        const page = reset
          ? await fetchGalleryPage(token, filter, debouncedQuery, { force: options.force })
          : await fetchGalleryNextPage(token, filter, debouncedQuery);
        if (gen !== genRef.current) return;
        if (!page) {
          if (reset && !cached) setError(true);
          return;
        }
        setItems(page.items);
        setHasMore(page.hasMore);
        setError(false);
      } finally {
        if (gen === genRef.current) {
          inFlightRef.current = false;
          setLoading(false);
          setLoadingMore(false);
        }
      }
    },
    [debouncedQuery, filter, token],
  );

  useFocusEffect(
    useCallback(() => {
      void load({ reset: true });
    }, [load]),
  );

  const refresh = useCallback(async () => {
    setPullRefreshing(true);
    await load({ reset: true, silent: true, force: true });
    setPullRefreshing(false);
  }, [load]);

  const loadMore = useCallback(() => {
    if (!hasMore || loadingMore || loading || inFlightRef.current) return;
    void load({ reset: false });
  }, [hasMore, load, loading, loadingMore]);

  const removeItem = useCallback((id: string) => {
    removeCachedGalleryItem(id);
    setItems((current) => current.filter((row) => row.id !== id));
  }, []);

  return {
    items,
    loading,
    loadingMore,
    error,
    pullRefreshing,
    refresh,
    loadMore,
    retry: load,
    removeItem,
  };
}
