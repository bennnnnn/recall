/**
 * Max wait for the WebSocket handshake before latching SSE.
 * Enterprise proxies that drop WS packets without a TCP reset used to
 * burn 8s before the first token. 1.5s still prefers WS on a healthy
 * path; a handshake that would have opened at 3s now uses SSE.
 */
export const WS_CONNECT_TIMEOUT_MS = 1_500;

/** Debounce eager connect so flicking the chat list does not open+auth+close per row. */
export const EAGER_CONNECT_DEBOUNCE_MS = 300;
