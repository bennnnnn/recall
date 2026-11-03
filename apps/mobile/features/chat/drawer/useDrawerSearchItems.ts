import { useEffect, useMemo, useRef } from "react";
import type { FlashListRef } from "@shopify/flash-list";

import type { DrawerChatListItem } from "@/features/chat/drawer/DrawerChatFlashList";
import type { SearchResult } from "@/lib/api";

const NO_ITEMS: DrawerChatListItem[] = [];

type Options = {
  searchOpen: boolean;
  searchQuery: string;
  searchResults: SearchResult[];
  searchHasMore: boolean;
  searchLoadingMore: boolean;
  searchLoadingMoreError: boolean;
  onOpenSearchResult: (id: string, messageId?: string | null) => void;
  onSearchLoadMore?: () => void;
};

/** The drawer list's search rows, and the list's ref that shows a new search from the top. */
export function useDrawerSearchItems({
  searchOpen,
  searchQuery,
  searchResults,
  searchHasMore,
  searchLoadingMore,
  searchLoadingMoreError,
  onOpenSearchResult,
  onSearchLoadMore,
}: Options) {
  // Each keystroke starts a new search with new result handlers. They ride on the search
  // items, so the chat rows under them keep their items and renderItem and are not redrawn.
  const searchItems = useMemo<DrawerChatListItem[]>(() => {
    if (!searchOpen || searchResults.length === 0) return NO_ITEMS;
    const items: DrawerChatListItem[] = [];
    for (const result of searchResults) {
      const key = result.message_id
        ? `search-${result.message_id}`
        : `search-title-${result.chat_id}`;
      items.push({ type: "searchRow", key, result, query: searchQuery, onOpen: onOpenSearchResult });
    }
    if (searchHasMore || searchLoadingMoreError) {
      items.push({
        type: "searchLoadMore",
        key: "search-load-more",
        loadingMore: searchLoadingMore,
        loadingMoreError: searchLoadingMoreError,
        onLoadMore: onSearchLoadMore,
      });
    }
    return items;
  }, [
    onOpenSearchResult,
    onSearchLoadMore,
    searchHasMore,
    searchLoadingMore,
    searchLoadingMoreError,
    searchOpen,
    searchQuery,
    searchResults,
  ]);

  // A new search's results go in above the chat rows. Keeping the rows on screen (the
  // list's visible-position rule, off while searching) pushed them out of sight. A new
  // first result is a new search: show it from the top. Load more keeps the place.
  const listRef = useRef<FlashListRef<DrawerChatListItem>>(null);
  const firstSearchKey = searchItems[0]?.key;
  useEffect(() => {
    if (firstSearchKey) listRef.current?.scrollToOffset({ offset: 0, animated: false });
  }, [firstSearchKey]);

  return { searchItems, listRef };
}
