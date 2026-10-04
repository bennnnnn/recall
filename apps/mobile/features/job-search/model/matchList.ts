import type { JobMatch } from "@/lib/api";

export type JobMatchFilter =
  "all" | "new" | "saved" | "applied" | "interviewing" | "offer" | "rejected";
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
      : filter === "saved"
        ? matches.filter((item) => item.is_saved && item.status !== "hidden")
        : filter === "new"
          ? matches.filter((item) => item.status === "new" && !item.is_saved)
          : matches.filter((item) => item.status === filter);
  const sorted = [...filtered];
  if (sort === "best") {
    // Unknown scores sink to the bottom; ties fall back to newest first.
    sorted.sort(
      (a, b) =>
        Number(b.match_kind === "qualifying") - Number(a.match_kind === "qualifying") ||
        b.match_reasons.length - a.match_reasons.length ||
        b.found_at.localeCompare(a.found_at),
    );
  } else {
    sorted.sort((a, b) => b.found_at.localeCompare(a.found_at));
  }
  return sorted;
}
