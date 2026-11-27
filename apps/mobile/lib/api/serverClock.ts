/**
 * The server's clock as this phone last saw it. A token's expiry is the server's time, and the
 * phone judged it by its own clock: one set an hour fast took every new token for expired and
 * refreshed before each request, until the server's refresh limit (10 a minute) refused every
 * request for a minute. The offset between the two is read from each answer's `Date` header
 * and from a new token's `iat` at the moment it arrives, and expiry is judged on the server's
 * clock (`tokenExpiry.ts`). Before any answer the phone's own clock stands in (offset 0).
 *
 * It is the phone's clock, not the account's: nothing here is cleared at sign-out.
 */

let offsetMs = 0;

/** The server said the time was `serverMs` when this phone's clock read `localMs`. */
export function noteServerTime(serverMs: number, localMs: number = Date.now()): void {
  if (!Number.isFinite(serverMs) || !Number.isFinite(localMs)) return;
  offsetMs = serverMs - localMs;
}

/** An answer's `Date` header (one-second precision; latency adds a little, well inside the
 * expiry's 30 s margin). An absent or unreadable one changes nothing. */
export function noteServerDateHeader(value: string | null | undefined, localMs: number = Date.now()): void {
  if (!value) return;
  const serverMs = Date.parse(value);
  if (!Number.isNaN(serverMs)) noteServerTime(serverMs, localMs);
}

/** The server's time now, by this phone's clock and the last offset seen. */
export function serverNow(localMs: number = Date.now()): number {
  return localMs + offsetMs;
}

/** For tests: back to the phone's own clock. */
export function resetServerClockForTest(): void {
  offsetMs = 0;
}
