import { useCallback, useRef, useState } from "react";
import { useFocusEffect } from "expo-router";

import { useAuth } from "@/contexts/AuthContext";
import { api, type AttachmentListItem } from "@/lib/api";
import type { GalleryFilter } from "@/lib/gallery";

export type { GalleryFilter };

const PAGE_SIZE = 30;

export function useGalleryData(filter: GalleryFilter) {
  const { token } = useAuth();
  const [items, setItems] = useState<AttachmentListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [pullRefreshing, setPullRefreshing] = useState(false);
  const offsetRef = useRef(0);

  const load = useCallback(
    async (options: { reset?: boolean; silent?: boolean } = {}) => {
      if (!token) return;
      const reset = options.reset ?? true;
      if (!options.silent) {
        if (reset) setLoading(true);
        else setLoadingMore(true);
      }
      try {
        const offset = reset ? 0 : offsetRef.current;
        const response = await api.listAttachments(token, {
          category: filter === "all" ? undefined : filter,
          limit: PAGE_SIZE,
          offset,
        });
        setItems((current) => (reset ? response.items : [...current, ...response.items]));
        setHasMore(response.has_more);
        offsetRef.current = offset + response.items.length;
        setError(false);
      } catch {
        setError(true);
      } finally {
        setLoading(false);
        setLoadingMore(false);
      }
    },
    [filter, token],
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
    if (!hasMore || loadingMore || loading) return;
    void load({ reset: false, silent: true });
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
