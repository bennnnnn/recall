/** Skip redundant list/home refetches when in-memory data is still fresh. */
export const CONTEXT_REFRESH_STALE_MS = 20_000;

export function isContextFresh(
  lastFetchedAt: number | undefined,
  now = Date.now(),
): boolean {
  return lastFetchedAt != null && now - lastFetchedAt < CONTEXT_REFRESH_STALE_MS;
}
