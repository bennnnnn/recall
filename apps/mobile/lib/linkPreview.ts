import { request } from "@/lib/api/client";
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
/** Previews kept; the oldest goes first. */
const MAX_PREVIEWS = 200;

type Entry =
  | { state: "ready"; preview: LinkPreview }
  | { state: "loading"; promise: Promise<LinkPreview> }
  | { state: "failed"; at: number };

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
  if (entry?.state === "failed" && Date.now() - entry.at < FAILURE_MEMORY_MS) {
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
    () => {
      if (cache.get(url) === loading) remember(url, { state: "failed", at: Date.now() });
    },
  );
  return promise;
}

/** Sign-out: the next account fetches its own previews. */
export function clearLinkPreviewCache(): void {
  cache.clear();
}
