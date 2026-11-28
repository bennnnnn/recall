/**
 * A JWT's claims, or null for an opaque or unreadable token: the one decode the phone makes of
 * an access token. Read only for hints (which account's cache to show, when the token expires),
 * never to authenticate or grant access.
 */
export function tokenClaims(token: string): Record<string, unknown> | null {
  try {
    const parts = token.split(".");
    if (parts.length !== 3 || parts.some((part) => !part)) return null;
    const payload = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const padded = payload.padEnd(Math.ceil(payload.length / 4) * 4, "=");
    const claims: unknown = JSON.parse(atob(padded));
    return typeof claims === "object" && claims !== null ? (claims as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

/**
 * The account id (`sub` claim) inside an access token, or null when it cannot
 * be read. Decoded only to pick which account's cached display data to show,
 * never to authenticate or grant access: a cache from a previous account can
 * survive a failed file deletion.
 */
export function tokenSubject(token: string): string | null {
  const sub = tokenClaims(token)?.sub;
  return typeof sub === "string" ? sub : null;
}
