import { serverNow } from "@/lib/api/serverClock";
import { tokenClaims } from "@/lib/tokenSubject";

function numericClaim(token: string, name: "exp" | "iat"): number | null {
  const value = tokenClaims(token)?.[name];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

/**
 * Decode JWT expiry only as a latency hint. Authentication still belongs to
 * the server; unreadable/opaque tokens keep the existing request-then-401
 * behavior instead of being rejected by the client. Judged on the server's
 * clock (`serverClock.ts`), so a phone clock set fast or slow does not take a
 * fresh token for an expired one, or the other way round.
 */
export function accessTokenNeedsRefresh(
  token: string,
  nowMs: number = serverNow(),
  skewMs = 30_000,
): boolean {
  const exp = numericClaim(token, "exp");
  if (exp === null) return false;
  return exp * 1000 <= nowMs + Math.max(0, skewMs);
}

/** When the server issued `token` (its `iat`), in ms; null without one. */
export function accessTokenIssuedAtMs(token: string): number | null {
  const iat = numericClaim(token, "iat");
  return iat === null ? null : iat * 1000;
}
