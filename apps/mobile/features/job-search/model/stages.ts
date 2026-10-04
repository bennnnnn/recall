import type { JobMatchStatus } from "@/lib/api";

export function hasApplied(status: JobMatchStatus): boolean {
  return status === "applied";
}

export function canToggleApplied(status: JobMatchStatus): boolean {
  return status === "new" || status === "applied";
}
