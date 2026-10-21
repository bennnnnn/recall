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

/** Server sends start before turn preparation. This bounds an OPEN but silent
 * connection without imposing a deadline on acknowledged model/tool work. */
export const WS_FIRST_EVENT_TIMEOUT_MS = 30_000;

/**
 * Once a turn's stream has started (socket or SSE), the longest it may go with
 * nothing. A quiet turn sends a `keepalive` every 15 s, so a longer silence is a
 * dead connection: the phone gives up on the stream and reloads the chat for the
 * reply the server saves (code-health audit NET-17).
 */
export const STREAM_IDLE_TIMEOUT_MS = 45_000;
