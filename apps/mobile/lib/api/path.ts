/**
 * Every API path that carries a value is built here, so no value can move the request to
 * another route (pre-launch review B1, 2026-11-27). A chat link's id `../chats`, pasted into
 * `/chats/${id}?if_empty=true`, became `DELETE /chats/../chats`, which Android's HTTP stack
 * resolves to `DELETE /chats`: every chat gone. The lint rule `recall/api-path`
 * (eslint.config.js) refuses a path built any other way.
 *
 *   apiPath`/chats/${chatId}/messages`            each value is one encoded segment
 *   withQuery(apiPath`/chats/${id}`, { if_empty: true })   a query from named values
 */

/**
 * A value that cannot be a segment: an empty one joins its neighbours (`/chats//pin`), and
 * a dot segment climbs once the URL is resolved, encoded or not (`%2e%2e` is `..` to the
 * URL standard and to OkHttp). Its path is marked with a NUL, which no encoded value holds,
 * and `requestRaw` refuses the path unsent (`isRefusedApiPath`).
 */
const UNUSABLE_SEGMENT = "\u0000";

function segment(value: string | number): string {
  const text = String(value);
  if (text === "" || /^\.+$/.test(text)) return UNUSABLE_SEGMENT;
  return encodeURIComponent(text);
}

/** A path from a template: each `${value}` becomes one encoded path segment. */
export function apiPath(strings: TemplateStringsArray, ...values: (string | number)[]): string {
  let path = strings[0] ?? "";
  values.forEach((value, index) => {
    path += segment(value) + (strings[index + 1] ?? "");
  });
  return path;
}

type QueryValue = string | number | boolean | null | undefined;

/** `path` with a query of `params`; a null or undefined value is left out, and so is an empty query. */
export function withQuery(path: string, params: Record<string, QueryValue>): string {
  const query = new URLSearchParams();
  for (const [name, value] of Object.entries(params)) {
    if (value !== null && value !== undefined) query.set(name, String(value));
  }
  const text = query.toString();
  return text ? `${path}?${text}` : path;
}

/** A path `apiPath` built from a value that cannot be a segment: never sent. */
export function isRefusedApiPath(path: string): boolean {
  return path.includes(UNUSABLE_SEGMENT);
}
