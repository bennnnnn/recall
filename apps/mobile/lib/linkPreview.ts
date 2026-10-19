import { requestRaw } from "@/lib/api/client";
import { getToken } from "@/lib/auth";

export type LinkPreview = {
  url: string;
  title: string | null;
  description: string | null;
  domain: string;
};

const cache = new Map<string, LinkPreview>();

/**
 * The server fetches `url` for its title. Ask only for a link
 * `lib/linkPreviewTrust.ts` allows (the user's own, or a search source).
 */
export async function fetchLinkPreview(url: string): Promise<LinkPreview> {
  const cached = cache.get(url);
  if (cached) return cached;

  // Route through lib/api's requestRaw so this fetch shares the REST path's
  // 401→refresh→retry behaviour and the lib/api boundary stays the single
  // network egress point (no bare fetch(getApiUrl()...) here).
  const token = await getToken();
  const res = await requestRaw(
    `/link-preview?url=${encodeURIComponent(url)}`,
    token,
  );
  if (!res.ok) throw new Error("preview failed");
  const data = (await res.json()) as LinkPreview;
  cache.set(url, data);
  return data;
}

/** Sign-out: the next account fetches its own previews. */
export function clearLinkPreviewCache(): void {
  cache.clear();
}
