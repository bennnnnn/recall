/**
 * What the chat socket carries, and what its closes mean (ChatWsTransport reads them): the
 * frames this phone sends, the server's turn events, and the close codes that decide whether
 * the next send opens a new socket, goes over SSE, or asks the connection check to look.
 */

/** The server's events of a turn: each one is news that the turn lives. */
export const WS_TURN_EVENT_TYPES: ReadonlySet<string> = new Set([
  "start",
  "status",
  "token",
  "reasoning",
  "stream_end",
  "done",
  "error",
  "duplicate",
  // Sent while a turn is quiet: proof of life, nothing to show.
  "keepalive",
]);

/** The socket's sign-in was refused (`ws_limits.socket_error_payload`): use SSE. */
export const WS_UNAUTHORIZED_CODE = "unauthorized";

/** The server closed a socket idle between turns (`ws_limits.WS_IDLE_CLOSE_CODE`). */
const WS_IDLE_CLOSE_CODE = 4408;
/** Over the per-user socket cap (`ws_limits.WS_TOO_MANY_SOCKETS_CLOSE_CODE`): use SSE. */
const WS_TOO_MANY_SOCKETS_CLOSE_CODE = 4429;
const WS_GOING_AWAY_CLOSE_CODE = 1001;
/** uvicorn's close when the server restarts (deploy): the next socket reaches the new machine. */
const WS_SERVICE_RESTART_CLOSE_CODE = 1012;
/** A deliberate close: the next send opens a new socket instead of falling back to SSE. */
export const RECONNECT_CLOSE_CODES: ReadonlySet<number> = new Set([
  WS_IDLE_CLOSE_CODE,
  WS_GOING_AWAY_CLOSE_CODE,
  WS_SERVICE_RESTART_CLOSE_CODE,
]);
/** Closes the server makes without reading a turn's frame: a send in flight is safe to replay. */
export const UNREAD_CLOSE_CODES: ReadonlySet<number> = new Set([
  WS_IDLE_CLOSE_CODE,
  WS_TOO_MANY_SOCKETS_CLOSE_CODE,
]);
/**
 * Closes that find no API, as a request's no answer or 502/503 does: no close frame (refused
 * or dropped), a gateway with nothing behind it (1014), and the server's Try Again Later (1013,
 * `ws_api._WS_TRY_AGAIN_LATER_CLOSE_CODE`: its Redis down). A deliberate close is none.
 */
export const OUTAGE_CLOSE_CODES: ReadonlySet<number> = new Set([1006, 1013, 1014]);

export type ChatWsAuthFrame = {
  token: string;
  client_timezone: string;
};

/** The phone's zone as a turn is sent: it can change while a socket stays open. */
type ChatWsTurnZone = { client_timezone: string };

export type ChatWsMessageFrame = ChatWsTurnZone & {
  type: "message";
  content: string;
  attachment_ids: string[];
  model: string | null;
  /** The message's name, the same on every send of it: the server runs one turn per name. */
  client_message_id: string;
  client_location: string | null;
  client_latitude: number | null;
  client_longitude: number | null;
};

export type ChatWsRegenerateFrame = ChatWsTurnZone & {
  type: "regenerate";
  model: string | null;
  client_location: string | null;
  client_latitude: number | null;
  client_longitude: number | null;
};
