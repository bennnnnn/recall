import { ApiRequestError } from "@/lib/api/client";

const NAMED_STATUSES = new Set([404, 429]);

const DETAIL_KEYS: Record<string, string> = {
  "Not available": "chat.chemistry_scan_unavailable",
  "Too many scans in a row. Try again in a few minutes.": "chat.chemistry_scan_rate_limit",
  "Reading photos is paused for now. Type the problem, or try again later.":
    "chat.chemistry_scan_spend_cap",
};

/**
 * 404 and 429 name themselves. A network failure, a vision failure, and
 * every other status stay the generic could-not-read message.
 */
export function chemistryScanFailureDetail(error: unknown): string | null {
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

/** Locale key for a known chemistry-scan detail. Unknown details stay as sent. */
export function chemistryScanFailureMessageKey(detail: string): string | null {
  return DETAIL_KEYS[detail] ?? null;
}
