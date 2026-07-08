/** Gate for re-fetching the model catalog on app foreground. */
export function shouldRefreshModels(
  lastFetchedAt: number,
  now: number,
  ttlMs: number,
): boolean {
  if (lastFetchedAt <= 0) return true;
  return now - lastFetchedAt >= ttlMs;
}
