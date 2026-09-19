import type { JobMatch } from "@/lib/api";

// Module-level snapshot of the last dashboard payload so the match detail
// screen opens instantly (StaleResourceCache pattern) and survives remounts.
const matchesById = new Map<string, JobMatch>();

export function cacheJobMatches(matches: readonly JobMatch[]): void {
  for (const match of matches) {
    matchesById.set(match.id, match);
  }
}

export function getCachedJobMatch(id: string): JobMatch | null {
  return matchesById.get(id) ?? null;
}

export function cacheJobMatch(match: JobMatch): void {
  matchesById.set(match.id, match);
}

export function clearJobMatchCache(): void {
  matchesById.clear();
}
