import { createListenerSet } from "@/lib/listenerSet";

/**
 * Requests that found no API. The connection check (hooks/useNetworkStatus.ts) ran on a
 * network change, a return to the app and while the banner showed, so an outage that began
 * with the app open went unseen: a read failed, no banner showed, and the list on screen was
 * not read again when the API came back (lib/reconnectRefresh.ts). The client
 * (lib/api/client.ts) reports each such failure here; the check coalesces them.
 */
const failures = createListenerSet();

/** A request got no answer, or a 502, 503 or 504. */
export function reportConnectionFailure(): void {
  failures.emit();
}

/** `listener` on each failure; returns its unsubscribe. */
export function onConnectionFailure(listener: () => void): () => void {
  return failures.subscribe(listener);
}
