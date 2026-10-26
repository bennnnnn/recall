import { request } from "@/lib/api/client";
import { ApiRequestError } from "@/lib/api/errorBody";
import { getToken } from "@/lib/auth";

export type LinkPreview = {
  url: string;
  title: string | null;
  description: string | null;
  domain: string;
};

/**
 * A failed preview is not asked for again for this long: a 429 or a dead page was
 * asked again each time its card scrolled back into view (code-health audit NET-19).
 */
const FAILURE_MEMORY_MS = 5 * 60_000;
/**
 * The server's code for "your other previews are still loading" (modules/link_preview/api.py):
 * not a failure of this link, so it is kept only as long as the server asked (its `Retry-After`);
 * a card on screen asks again when that ends (`busyPreviewRetryAt`), one shown later asks then.
 * Kept for five minutes, a reply with four or more links showed plain links that long.
 */
const BUSY_CODE = "link_preview_busy";
/** The wait the server states for a busy refusal (`_BUSY_RETRY_AFTER_SECONDS`), when the header is lost. */
const BUSY_FALLBACK_MS = 8_000;
/**
 * The longest a busy refusal is kept: the fetches it waits on end within the server's 8 s
 * deadline and stop counting after 30 s at most, so a longer header is a wrong one.
 */
const BUSY_MAX_MS = 60_000;
/** Previews kept; the oldest goes first. */
const MAX_PREVIEWS = 200;

type Entry =
  | { state: "ready"; preview: LinkPreview }
  | { state: "loading"; promise: Promise<LinkPreview> }
  | { state: "failed"; until: number; busy: boolean };

const cache = new Map<string, Entry>();

function remember(url: string, entry: Entry): void {
  cache.delete(url);
  cache.set(url, entry);
  while (cache.size > MAX_PREVIEWS) cache.delete(cache.keys().next().value as string);
}

/**
 * The server fetches `url` for its title. Ask only for a link
 * `lib/linkPreviewTrust.ts` allows (the user's own, or a search source).
 * Cards showing the same link share one request. A card that leaves the screen
 * does not cancel it: the preview it brings is kept for when the card comes back.
 */
export function fetchLinkPreview(url: string): Promise<LinkPreview> {
  const entry = cache.get(url);
  if (entry?.state === "ready") return Promise.resolve(entry.preview);
  if (entry?.state === "loading") return entry.promise;
  if (entry?.state === "failed" && Date.now() < entry.until) {
    return Promise.reject(new Error("preview failed"));
  }
  const promise = (async () => {
    const token = await getToken();
    if (!token) throw new Error("preview failed");
    return request<LinkPreview>(`/link-preview?url=${encodeURIComponent(url)}`, token);
  })();
  const loading: Entry = { state: "loading", promise };
  remember(url, loading);
  // Only this request's own entry is settled: sign-out may have cleared it since.
  promise.then(
    (preview) => {
      if (cache.get(url) === loading) remember(url, { state: "ready", preview });
    },
    (error: unknown) => {
      if (cache.get(url) !== loading) return;
      const busy = isBusy(error);
      remember(url, { state: "failed", until: Date.now() + (busy ? busyMemoryMs(error) : FAILURE_MEMORY_MS), busy });
    },
  );
  return promise;
}

function isBusy(error: unknown): error is ApiRequestError {
  return error instanceof ApiRequestError && error.code === BUSY_CODE;
}

/** How long a busy refusal is kept: the server's wait, at most a minute. */
function busyMemoryMs(error: ApiRequestError): number {
  return Math.min(error.retryAfterMs ?? BUSY_FALLBACK_MS, BUSY_MAX_MS);
}

/**
 * When `url`'s busy refusal may be asked again (ms since the epoch), or null when its last
 * answer was not a busy refusal: a dead page or the rate limit is never asked again on screen.
 */
export function busyPreviewRetryAt(url: string): number | null {
  const entry = cache.get(url);
  return entry?.state === "failed" && entry.busy ? entry.until : null;
}

/** Sign-out: the next account fetches its own previews. */
export function clearLinkPreviewCache(): void {
  cache.clear();
}
