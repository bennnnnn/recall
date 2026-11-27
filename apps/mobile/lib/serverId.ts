/** The ids the API mints for chats, messages, to-dos and attachments: UUIDs. */
const SERVER_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** An id the API minted (not a `streaming` or `local-*` stand-in, nor anything a link wrote). */
export function isServerId(id: unknown): id is string {
  return typeof id === "string" && SERVER_ID.test(id);
}

/**
 * The id a route or deep-link param names, or none. A link can carry any text
 * (`recall://?chatId=..%2Fchats`), and the chat it opened once became `DELETE /chats` (pre-launch
 * review B1, 2026-11-27): anything but one server id names no such item, so the screen opens
 * as it does with none (a fresh chat, the whole list).
 */
export function routeServerId(param: string | string[] | undefined): string | undefined {
  return isServerId(param) ? param : undefined;
}
