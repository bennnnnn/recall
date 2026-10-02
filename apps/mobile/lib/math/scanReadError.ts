import { ApiRequestError } from "@/lib/api/client";

/** A scan the API refused, with the detail the student should see. */
export type MathScanReadFailure = { error: string };

const LIMIT_STATUSES = new Set([413, 429]);

/**
 * The scan read API names a rate limit (429) and an oversized photo (413).
 * A network failure and an empty 200 stay generic, so this returns nothing
 * for every other error.
 */
export function mathScanFailureDetail(error: unknown): string | null {
  if (!(error instanceof ApiRequestError) || !LIMIT_STATUSES.has(error.status)) return null;
  const raw = error.message.trim();
  if (!raw.startsWith("{")) return null;
  try {
    const body = JSON.parse(raw) as { detail?: unknown };
    const detail = body.detail;
    return typeof detail === "string" && detail.trim() ? detail.trim() : null;
  } catch {
    return null;
  }
}
