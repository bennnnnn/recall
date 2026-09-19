import type { JobMatch } from "@/lib/api";

export type JobMatchFilter = "all" | "new" | "saved" | "applied";
export type JobMatchSort = "best" | "newest";

/** Dashboard list shaping: status filter, then best-fit or newest ordering. */
export function filterAndSortMatches(
  matches: readonly JobMatch[],
  filter: JobMatchFilter,
  sort: JobMatchSort,
): JobMatch[] {
  const filtered =
    filter === "all"
      ? matches.filter((item) => item.status !== "hidden")
      : matches.filter((item) => item.status === filter);
  const sorted = [...filtered];
  if (sort === "best") {
    // Unknown scores sink to the bottom; ties fall back to newest first.
    sorted.sort(
      (a, b) =>
        (b.match_score ?? -1) - (a.match_score ?? -1) ||
        b.found_at.localeCompare(a.found_at),
    );
  } else {
    sorted.sort((a, b) => b.found_at.localeCompare(a.found_at));
  }
  return sorted;
}
