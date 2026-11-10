/**
 * Max wait for the WebSocket handshake before sends go over SSE.
 * A send opens its chat's socket (none is kept open while the chat is only read or
 * typed in), and a healthy one opens well inside this budget. It still covers a
 * handshake's round trips on high-latency cellular (a tighter budget failed there and
 * pushed the chat onto SSE), while a path that silently drops WS costs one send this
 * long before SSE (the backoff then keeps later sends off the socket).
 */
export const WS_CONNECT_TIMEOUT_MS = 2_500;

/** A socket that opens after its chat left the screen is kept this long, for a send already tapped. */
export const WS_LINGER_MS = 5_000;

/**
 * While its chat is on screen, a socket is kept this long after it opened (a draft's first
 * character opens it) or its last turn ended: the next message reuses it instead of paying a
 * new handshake (TLS in production) before its first token. Leaving the chat or the app
 * closes it at once.
 */
export const WS_IDLE_KEEP_MS = 60_000;

/** Server sends start before turn preparation. This bounds an OPEN but silent
 * connection without imposing a deadline on acknowledged model/tool work. */
export const WS_FIRST_EVENT_TIMEOUT_MS = 30_000;

/** The server answers a send with `start` at once; this long without it, the
 * socket is probed instead of waiting out the first-event deadline. */
export const WS_ACK_PROBE_MS = 3_000;

/** A probe's ping unanswered this long: the socket is dead (often half-open
 * after a Wi-Fi/cellular switch) and the send is replayed. */
export const WS_PROBE_TIMEOUT_MS = 3_000;

/** A saved reply's follow-up questions, and a new chat's title, come on its socket after
 * `done` (the server gives the questions' model call 6 s and waits 8 s for the title): the
 * socket is kept this long for them at most, then let go. */
export const WS_FOLLOW_UPS_WAIT_MS = 10_000;

/**
 * A reply's photo still on its way at `done` (`photo_pending`) comes after it as an
 * `answer_photo` event: the server gives its search 20 s from the reply's end
 * (`answer_photo.LATE_PHOTO_SECONDS`), and `done` comes at least 2 s after that end (the
 * reply's wait for its photo), so the photo is in by this long after `done`. The reply's
 * placeholder waits this long for it.
 */
export const ANSWER_PHOTO_WAIT_MS = 20_000;

/**
 * Once a turn's stream has started (socket or SSE), the longest it may go with
 * nothing. A quiet turn sends a `keepalive` every 15 s, so a longer silence is a
 * dead connection: the phone gives up on the stream and reloads the chat for the
 * reply the server saves (code-health audit NET-17).
 */
export const STREAM_IDLE_TIMEOUT_MS = 45_000;
