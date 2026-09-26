import type { JobMatchStatus } from "@/lib/api";

const APPLIED_STAGES = new Set<JobMatchStatus>([
  "applied",
  "interviewing",
  "offer",
  "rejected",
]);

/** Later pipeline stages still mean the user has applied. */
export function hasApplied(status: JobMatchStatus): boolean {
  return APPLIED_STAGES.has(status);
}

/** Only the first pipeline step can be toggled without losing later progress. */
export function canToggleApplied(status: JobMatchStatus): boolean {
  return status === "new" || status === "applied";
}
