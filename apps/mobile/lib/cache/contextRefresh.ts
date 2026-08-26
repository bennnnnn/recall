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
  // New chat and Back from Learning / Reminders / Lists land on Home.
  // Reuse the login /home payload — the 20s window goes stale while a
  // thread or those screens are open.
  if (opts.hasFetchedHome) return false;
  return true;
}
