import type { SearchResult } from "@/lib/api";

export const DRAWER_SEARCH_DEBOUNCE_MS = 300;
export const DRAWER_SEARCH_PAGE_SIZE = 20;
export const DRAWER_SEARCH_MIN_LENGTH = 2;
export const DRAWER_SEARCH_MAX_LENGTH = 200;
export const DRAWER_SEARCH_MAX_OFFSET = 10_000;

/** Python's request bounds count Unicode code points, not UTF-16 code units. */
export function isValidDrawerSearchQuery(query: string): boolean {
  const length = Array.from(query.trim()).length;
  return length >= DRAWER_SEARCH_MIN_LENGTH && length <= DRAWER_SEARCH_MAX_LENGTH;
}

export function isAbortError(error: unknown): boolean {
  if (error instanceof Error && error.name === "AbortError") return true;
  return typeof DOMException !== "undefined" && error instanceof DOMException && error.name === "AbortError";
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

export function hasMoreDrawerSearchResults(nextOffset: number, total: number, lastPageSize: number): boolean {
  return lastPageSize > 0 && nextOffset < total && nextOffset <= DRAWER_SEARCH_MAX_OFFSET;
}
