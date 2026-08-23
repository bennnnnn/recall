import { useCallback, useEffect, useRef, useState } from "react";
import { useFocusEffect } from "expo-router";

import { useAuth } from "@/contexts/AuthContext";
import { api, type AttachmentListItem } from "@/lib/api";
import {
  GALLERY_SEARCH_DEBOUNCE_MS,
  galleryListParams,
  mergeGalleryItems,
  type GalleryFilter,
} from "@/lib/gallery";

export type { GalleryFilter };

const PAGE_SIZE = 30;

export function useGalleryData(filter: GalleryFilter, searchQuery: string) {
  const { token } = useAuth();
  const trimmedQuery = searchQuery.trim();
  const [debouncedQuery, setDebouncedQuery] = useState(trimmedQuery);
  const [items, setItems] = useState<AttachmentListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [pullRefreshing, setPullRefreshing] = useState(false);
  const offsetRef = useRef(0);
  const inFlightRef = useRef(false);
  const genRef = useRef(0);

  useEffect(() => {
    const handle = setTimeout(() => setDebouncedQuery(trimmedQuery), GALLERY_SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(handle);
  }, [trimmedQuery]);

  const load = useCallback(
    async (options: { reset?: boolean; silent?: boolean } = {}) => {
      if (!token) return;
      const reset = options.reset ?? true;
      if (!reset && inFlightRef.current) return;
      if (reset) genRef.current += 1;
      const gen = genRef.current;
      inFlightRef.current = true;
      if (!options.silent) {
        if (reset) setLoading(true);
        else setLoadingMore(true);
      }
      try {
        const offset = reset ? 0 : offsetRef.current;
        const response = await api.listAttachments(token, {
          ...galleryListParams(filter),
          ...(debouncedQuery ? { q: debouncedQuery } : {}),
          limit: PAGE_SIZE,
          offset,
        });
        if (gen !== genRef.current) return;
        setItems((current) => mergeGalleryItems(current, response.items, reset));
        setHasMore(response.has_more);
        offsetRef.current = offset + response.items.length;
        setError(false);
      } catch {
        if (gen !== genRef.current) return;
        if (reset) setError(true);
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
    await load({ reset: true, silent: true });
    setPullRefreshing(false);
  }, [load]);

  const loadMore = useCallback(() => {
    if (!hasMore || loadingMore || loading || inFlightRef.current) return;
    void load({ reset: false });
  }, [hasMore, load, loading, loadingMore]);

  return {
    items,
    loading,
    loadingMore,
    error,
    pullRefreshing,
    refresh,
    loadMore,
    retry: load,
  };
}
