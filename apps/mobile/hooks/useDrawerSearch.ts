import { useCallback, useEffect, useRef, useState, type RefObject } from "react";
import type { TextInput } from "react-native";

import { api, type SearchResult } from "@/lib/api";
import {
  DRAWER_SEARCH_DEBOUNCE_MS,
  isAbortError,
  shouldApplyDrawerSearchResult,
} from "@/lib/drawerSearchLogic";
import { registerDrawerSearch } from "@/lib/drawer";

type Options = {
  token: string | null;
  isDrawerOpen: boolean;
};

export function useDrawerSearch({ token, isDrawerOpen }: Options) {
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState(false);
  const searchInputRef = useRef<TextInput>(null);
  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const searchAbortRef = useRef<AbortController | null>(null);
  const searchGenerationRef = useRef(0);

  const cancelPendingSearch = useCallback(() => {
    if (searchTimerRef.current) {
      clearTimeout(searchTimerRef.current);
      searchTimerRef.current = null;
    }
    searchAbortRef.current?.abort();
    searchAbortRef.current = null;
  }, []);

  const closeSearch = useCallback(() => {
    cancelPendingSearch();
    searchGenerationRef.current += 1;
    setSearchOpen(false);
    setSearchQuery("");
    setSearchResults([]);
    setSearchError(false);
    setSearchLoading(false);
  }, [cancelPendingSearch]);

  const openSearch = useCallback(() => {
    setSearchOpen(true);
    requestAnimationFrame(() => searchInputRef.current?.focus());
  }, []);

  useEffect(() => {
    registerDrawerSearch(openSearch);
    return () => registerDrawerSearch(null);
  }, [openSearch]);

  const doSearch = useCallback(
    async (q: string, generation: number) => {
      if (!token || !q.trim()) {
        if (shouldApplyDrawerSearchResult(generation, searchGenerationRef.current)) {
          setSearchResults([]);
          setSearchError(false);
          setSearchLoading(false);
        }
        return;
      }

      const controller = new AbortController();
      searchAbortRef.current = controller;
      setSearchLoading(true);
      setSearchError(false);

      try {
        const data = await api.search(token, q.trim(), 20, {
          signal: controller.signal,
        });
        if (!shouldApplyDrawerSearchResult(generation, searchGenerationRef.current)) {
          return;
        }
        setSearchResults(data.results);
      } catch (error: unknown) {
        if (isAbortError(error)) return;
        if (!shouldApplyDrawerSearchResult(generation, searchGenerationRef.current)) {
          return;
        }
        setSearchError(true);
        setSearchResults([]);
      } finally {
        if (shouldApplyDrawerSearchResult(generation, searchGenerationRef.current)) {
          setSearchLoading(false);
        }
        if (searchAbortRef.current === controller) {
          searchAbortRef.current = null;
        }
      }
    },
    [token],
  );

  const onSearchChange = useCallback(
    (text: string) => {
      setSearchQuery(text);
      cancelPendingSearch();
      searchTimerRef.current = setTimeout(() => {
        const generation = ++searchGenerationRef.current;
        void doSearch(text, generation);
      }, DRAWER_SEARCH_DEBOUNCE_MS);
    },
    [cancelPendingSearch, doSearch],
  );

  useEffect(() => {
    if (!isDrawerOpen) closeSearch();
  }, [isDrawerOpen, closeSearch]);

  useEffect(() => {
    return () => {
      cancelPendingSearch();
      searchGenerationRef.current += 1;
    };
  }, [cancelPendingSearch]);

  const hasSearchQuery = searchQuery.trim().length > 0;

  return {
    searchOpen,
    searchQuery,
    searchResults,
    searchLoading,
    searchError,
    hasSearchQuery,
    searchInputRef: searchInputRef as RefObject<TextInput>,
    openSearch,
    closeSearch,
    onSearchChange,
  };
}
