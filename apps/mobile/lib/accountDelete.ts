import { isServiceUnavailable } from "@/lib/api/errorBody";

/** Sessions are purged first on the server — a 401/404 here means the wipe already started. */
export function isAccountDeleteComplete(error: unknown): boolean {
  if (typeof error !== "object" || error === null || !("status" in error)) {
    return false;
  }
  const status = error.status;
  return status === 401 || status === 404;
}

/** Why a delete did not happen. */
export type AccountDeleteFailure = "unavailable" | "failed";

/**
 * A refused delete: Recall could not serve it for now (its 503 `unavailable`, refused before
 * anything was deleted when the usage carry-over or the session purge cannot reach Redis,
 * or a gateway's 502/503/504), or anything else.
 */
export function accountDeleteFailure(error: unknown): AccountDeleteFailure {
  return isServiceUnavailable(error) ? "unavailable" : "failed";
}

/** The line a refused delete says: try again in a moment, or that it failed. */
export function accountDeleteFailureKey(failure: AccountDeleteFailure): string {
  return failure === "unavailable" ? "common.service_unavailable" : "settings.delete_failed";
}
