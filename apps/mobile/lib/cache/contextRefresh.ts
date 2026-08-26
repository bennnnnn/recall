/** Skip redundant list/home refetches when in-memory data is still fresh. */
export const CONTEXT_REFRESH_STALE_MS = 20_000;

export function isContextFresh(
  lastFetchedAt: number | undefined,
  now = Date.now(),
): boolean {
  return lastFetchedAt != null && now - lastFetchedAt < CONTEXT_REFRESH_STALE_MS;
}

/** Home starters are not on screen when a thread is open. */
export function shouldRefreshHomeOnChatFocus(opts: {
  hasOpenThread: boolean;
  hasFetchedHome?: boolean;
}): boolean {
  if (opts.hasOpenThread) return false;
  // New chat shows Home; reuse the login /home payload instead of refetching
  // because we skipped Home while a thread was open.
  if (opts.hasFetchedHome) return false;
  return true;
}
