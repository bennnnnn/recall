/**
 * Max wait for the WebSocket handshake before latching SSE.
 * A healthy socket should open well inside this budget; a proxy/network path
 * that silently drops WS must not add a multi-second penalty before SSE.
 */
export const WS_CONNECT_TIMEOUT_MS = 900;

/**
 * Start the eager socket almost immediately after a chat becomes active so
 * navigation/typing time hides the handshake, while keeping a small debounce
 * to avoid opening a socket for every row during a fast list fling.
 */
export const EAGER_CONNECT_DEBOUNCE_MS = 100;
