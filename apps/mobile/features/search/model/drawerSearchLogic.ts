import type { SearchResult } from "@/lib/api";

export const DRAWER_SEARCH_DEBOUNCE_MS = 300;
export const DRAWER_SEARCH_PAGE_SIZE = 20;
// The server's minimum: a trigram index cannot narrow a shorter substring.
const DRAWER_SEARCH_MIN_LENGTH = 3;
const DRAWER_SEARCH_MAX_LENGTH = 200;
const DRAWER_SEARCH_MAX_OFFSET = 10_000;

/** Python's request bounds count Unicode code points, not UTF-16 code units. */
export function isValidDrawerSearchQuery(query: string): boolean {
  const length = Array.from(query.trim()).length;
  return length >= DRAWER_SEARCH_MIN_LENGTH && length <= DRAWER_SEARCH_MAX_LENGTH;
}

/** Stable display identity; offsets still count every row consumed from the API. */
export function mergeDrawerSearchResults(previous: SearchResult[], incoming: SearchResult[]): SearchResult[] {
  const byId = new Map<string, SearchResult>();
  for (const result of [...previous, ...incoming]) {
    const id = result.message_id ? `message:${result.chat_id}:${result.message_id}` : `title:${result.chat_id}`;
    byId.set(id, result);
  }
  return [...byId.values()];
}

/** The server says whether hits follow the page (it reads one row past it, never a count). */
export function hasMoreDrawerSearchResults(nextOffset: number, hasMore: boolean, lastPageSize: number): boolean {
  return lastPageSize > 0 && hasMore && nextOffset <= DRAWER_SEARCH_MAX_OFFSET;
}
