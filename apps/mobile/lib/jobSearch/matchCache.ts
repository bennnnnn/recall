import type { JobMatch } from "@/lib/api";

// Module-level snapshot of the last dashboard payload so the match detail
// screen opens instantly (StaleResourceCache pattern) and survives remounts.
const matchesByAccount = new Map<string, Map<string, JobMatch>>();

function accountMatches(accountId: string): Map<string, JobMatch> {
  const cached = matchesByAccount.get(accountId);
  if (cached) return cached;
  const created = new Map<string, JobMatch>();
  matchesByAccount.set(accountId, created);
  return created;
}

export function cacheJobMatches(accountId: string, matches: readonly JobMatch[]): void {
  const matchesById = accountMatches(accountId);
  for (const match of matches) {
    matchesById.set(match.id, match);
  }
}

export function getCachedJobMatch(accountId: string, id: string): JobMatch | null {
  return matchesByAccount.get(accountId)?.get(id) ?? null;
}

export function cacheJobMatch(accountId: string, match: JobMatch): void {
  accountMatches(accountId).set(match.id, match);
}

export function clearJobMatchCache(): void {
  matchesByAccount.clear();
}
