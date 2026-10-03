import { ApiRequestError } from "@/lib/api/client";

/** A scan the API refused, with the message the student should see. */
export type ScanReadFailure = { error: string };

// Every subject's read endpoint shares one protocol (services/scan_read.py): 404 when the
// reader is off, 413 for an oversized photo, 429 for the rate limit or the spend cap.
const NAMED_STATUSES = new Set([404, 413, 429]);

const DETAIL_KEYS: Record<string, string> = {
  "Not available": "chat.scan_unavailable",
  "Image too large": "chat.scan_too_large",
  "Too many scans in a row. Try again in a few minutes.": "chat.scan_rate_limit",
  "Reading photos is paused for now. Type the problem, or try again later.":
    "chat.scan_spend_cap",
};

/**
 * The detail the API named for a refused scan, for any subject. A network
 * failure, a vision failure, and every other status stay the generic
 * could-not-read message, so this returns nothing for them.
 */
export function scanFailureDetail(error: unknown): string | null {
  if (!(error instanceof ApiRequestError) || !NAMED_STATUSES.has(error.status)) return null;
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

/** Locale key for a known scan detail. An unknown detail is shown as sent. */
export function scanFailureMessageKey(detail: string): string | null {
  return DETAIL_KEYS[detail] ?? null;
}
