/**
 * Which build this is, on every call to our API (`X-App-Version`; a chat socket's is an
 * `app_version` query parameter, as its request id is). The API names it on every log line
 * of the call and a turn can read it (apps/api/app/core/client_version.py), so a reply this
 * build cannot draw can be told apart by build. A version and build, never content.
 */
export const APP_VERSION_HEADER = "X-App-Version";

/** The API's rule for a version it reads (core/client_version.py _APP_VERSION_RE). */
const APP_VERSION = /^[0-9A-Za-z._+-]{1,32}$/;

let tag: string | null | undefined;

/** The app's version and build, read when first asked: the API client also loads in
 * plain-node tests, where expo-constants cannot. */
function readAppVersion(): { version: string; build: string | null } | null {
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports -- lazy, for the reason above
    return (require("@/lib/appVersion") as typeof import("@/lib/appVersion")).appVersion();
  } catch (error) {
    // expo-constants does not load here (a plain-node test): no build name to send.
    if (error instanceof Error) return null;
    throw error;
  }
}

/** "1.0.0+42": the version and its native build (the version alone in Expo Go). */
function appVersionTag(): string | null {
  if (tag !== undefined) return tag;
  const app = readAppVersion();
  const value = !app ? "" : app.build ? `${app.version}+${app.build}` : app.version;
  tag = APP_VERSION.test(value) ? value : null;
  return tag;
}

/** The header naming this build, or none when the build has no well-formed name. */
export function appVersionHeaders(): Record<string, string> {
  const value = appVersionTag();
  return value ? { [APP_VERSION_HEADER]: value } : {};
}

/** `url` with this build as its `app_version` query parameter (a chat socket's). */
export function withAppVersion(url: string): string {
  const value = appVersionTag();
  if (!value) return url;
  const [base, hash] = url.split("#", 2);
  const joined = `${base}${base.includes("?") ? "&" : "?"}app_version=${encodeURIComponent(value)}`;
  return hash === undefined ? joined : `${joined}#${hash}`;
}
